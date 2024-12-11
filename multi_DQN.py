import random
import gym
import numpy as np
import collections
from tqdm import tqdm
import torch
import torch.nn.functional as F
import matplotlib.pyplot as plt
import rl_utils
from new_env import BeerGame
from gym import error, spaces
from gym.utils import seeding
from collections import deque
import itertools

from env_cfg import Config, TestDemand, Agent

class ReplayBuffer:
    ''' 经验回放池 '''
    def __init__(self, capacity):
        self.buffer = collections.deque(maxlen=capacity)  # 队列,先进先出

    def add(self, state, action, reward, next_state, done):  # 将数据加入buffer
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size):  # 从buffer中采样数据,数量为batch_size
        transitions = random.sample(self.buffer, batch_size)
        state, action, reward, next_state, done = zip(*transitions)
        return np.array(state), action, reward, np.array(next_state), done

    def size(self):  # 目前buffer中数据的数量
        return len(self.buffer)

class Qnet(torch.nn.Module):
    ''' 只有一层隐藏层的Q网络 '''
    def __init__(self, state_dim, hidden_dim, action_dim):
        super(Qnet, self).__init__()
        self.fc1 = torch.nn.Linear(state_dim, hidden_dim)
        self.fc2 = torch.nn.Linear(hidden_dim, action_dim)

    # def __init__(self, state_dim, hidden_dim, action_dim):
    #     super(Qnet, self).__init__()
    #     self.fc1 = torch.nn.Linear(state_dim, hidden_dim)
    #     self.fc2 = torch.nn.Linear(hidden_dim, 2*hidden_dim)
    #     self.fc3 = torch.nn.Linear(2*hidden_dim, action_dim)
    
    # def forward(self, x):
    #     x = F.relu(self.fc1(x))
    #     x = F.relu(self.fc2(x))
    #     return self.fc3(x)


    def forward(self, x):
        x = F.relu(self.fc1(x))  # 隐藏层使用ReLU激活函数
        return self.fc2(x)

class DQN:
    ''' DQN算法 '''
    def __init__(self, state_dim, hidden_dim, action_dim, learning_rate, gamma,
                 epsilon, target_update, device):
        self.action_dim = action_dim
        self.q_net = Qnet(state_dim, hidden_dim,
                          self.action_dim).to(device)  # Q网络
        # 目标网络
        self.target_q_net = Qnet(state_dim, hidden_dim,
                                 self.action_dim).to(device)
        # 使用Adam优化器
        self.optimizer = torch.optim.Adam(self.q_net.parameters(),
                                          lr=learning_rate)
        self.gamma = gamma  # 折扣因子
        self.epsilon = epsilon  # epsilon-贪婪策略
        self.target_update = target_update  # 目标网络更新频率
        self.count = 0  # 计数器,记录更新次数
        self.device = device

    def take_action(self, state):  # epsilon-贪婪策略采取动作
        if np.random.random() < self.epsilon:
            action = np.random.randint(self.action_dim)
        else:
            state = torch.tensor([state], dtype=torch.float).to(self.device)
            # print("state", state.shape)
            # print(self.q_net(state).shape)
            action = self.q_net(state).argmax().item()
        # print("action",action)
        return action

    def update(self, transition_dict):
        states = torch.tensor(transition_dict['states'],
                              dtype=torch.float).to(self.device)
        actions = torch.tensor(transition_dict['actions']).view(-1, 1).to(
            self.device)
        rewards = torch.tensor(transition_dict['rewards'],
                               dtype=torch.float).view(-1, 1).to(self.device)
        next_states = torch.tensor(transition_dict['next_states'],
                                   dtype=torch.float).to(self.device)
        dones = torch.tensor(transition_dict['dones'],
                             dtype=torch.float).view(-1, 1).to(self.device)
        # print(self.q_net(states).shape)
        q_values = self.q_net(states).gather(1, actions)  # Q值
        # q_values = self.q_net(states).gather(2, actions.unsqueeze(2))

        # 下个状态的最大Q值
        max_next_q_values = self.target_q_net(next_states).max(1)[0].view(
            -1, 1)
        q_targets = rewards + self.gamma * max_next_q_values * (1 - dones
                                                                )  # TD误差目标
        dqn_loss = torch.mean(F.mse_loss(q_values, q_targets))  # 均方误差损失函数
        self.optimizer.zero_grad()  # PyTorch中默认梯度会累积,这里需要显式将梯度置为0
        dqn_loss.backward()  # 反向传播更新参数
        self.optimizer.step()

        if self.count % self.target_update == 0:
            self.target_q_net.load_state_dict(
                self.q_net.state_dict())  # 更新目标网络
        self.count += 1

lr = 4e-4
num_episodes = 2000
hidden_dim = 128
gamma = 0.98
epsilon = 0.01
target_update = 10
buffer_size = 10000
minimal_size = 100
batch_size = 64
device = torch.device("cuda") if torch.cuda.is_available() else torch.device(
    "cpu")

env = BeerGame()
obs = env.reset()
env.render()
done = False

random.seed(0)
np.random.seed(0)
env.seed(0)
torch.manual_seed(0)
replay_buffer = ReplayBuffer(buffer_size)
state_dim = 50
action_dim = 5
actions = [-2,-1,0,1,2]

agent = DQN(state_dim, hidden_dim, action_dim, lr, gamma, epsilon,
            target_update, device)

return_list = []
for i in range(10):
    with tqdm(total=int(num_episodes / 10), desc='Iteration %d' % i) as pbar:
        for i_episode in range(int(num_episodes / 10)):
            episode_return = 0
            state = env.reset()
            # state = np.array(state)
            # state = state.reshape(1, -1)
            # print(state.shape)
            done = False
            while not done:
                # print(state)
                # exit(0)
                action = agent.take_action(state[0])
                action = (action,random.randint(0,4),random.randint(0,4),random.randint(0,4))
                # print(action)
                next_state, reward, done, _ = env.step(action,0)
                
                # print(next_state)
                # exit(0)
                # next_state = np.array(next_state)
                # next_state = next_state.reshape(1, -1)
                replay_buffer.add(state[0], action[0], reward[0], next_state[0], done[0])
                done = all(done)
                state = next_state
                episode_return += sum(reward)
                # 当buffer数据的数量超过一定值后,才进行Q网络训练
                if replay_buffer.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent.update(transition_dict)
            return_list.append(episode_return)
            if (i_episode + 1) % 10 == 0:
                pbar.set_postfix({
                    'episode':
                    '%d' % (num_episodes / 10 * i + i_episode + 1),
                    'return':
                    '%.3f' % np.mean(return_list[-10:])
                })
            pbar.update(1)
    env.render()

#将训练得到的agent保存到文件中
torch.save(agent.q_net.state_dict(), 'dqn_agent.pth')

#绘制训练过程中的回报曲线
plt.figure()
plt.plot(return_list)
plt.xlabel('Episode')
plt.ylabel('Return')
plt.show()

#计算平均回报
return_list = np.array(return_list).reshape(-1, 10)
average_return = np.mean(return_list, axis=1)
print('Average return:', average_return)
print('Average return over the last 10 episodes:',
      np.mean(average_return[-10:]))

agent2 = DQN(state_dim, hidden_dim, action_dim, lr, gamma, epsilon,
            target_update, device)
return_list = []
for i in range(10):
    with tqdm(total=int(num_episodes / 10), desc='Iteration %d' % i) as pbar:
        for i_episode in range(int(num_episodes / 10)):
            episode_return = 0
            state = env.reset()
            done = False
            while not done:
                action1 = agent.take_action(state[0])
                action2 = agent2.take_action(state[1])
                action = (action1,action2,random.randint(0,4),random.randint(0,4))
                next_state, reward, done, _ = env.step(action,1)
                replay_buffer.add(state[1], action[1], reward[1], next_state[1], done[1])
                done = all(done)
                state = next_state
                episode_return += sum(reward)
                if replay_buffer.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent2.update(transition_dict)
            return_list.append(episode_return)
            if (i_episode + 1) % 10 == 0:
                pbar.set_postfix({
                    'episode':
                    '%d' % (num_episodes / 10 * i + i_episode + 1),
                    'return':
                    '%.3f' % np.mean(return_list[-10:])
                })
            pbar.update(1)
    env.render()

#将训练得到的agent保存到文件中
torch.save(agent2.q_net.state_dict(), 'dqn_agent2.pth')

#绘制训练过程中的回报曲线
plt.figure()
plt.plot(return_list)
plt.xlabel('Episode')
plt.ylabel('Return')
plt.show()

#计算平均回报
return_list = np.array(return_list).reshape(-1, 10)
average_return = np.mean(return_list, axis=1)
print('Average return:', average_return)
print('Average return over the last 10 episodes:',
      np.mean(average_return[-10:]))


agent3 = DQN(state_dim, hidden_dim, action_dim, lr, gamma, epsilon,
            target_update, device)
return_list = []

for i in range(10):
    with tqdm(total=int(num_episodes / 10), desc='Iteration %d' % i) as pbar:
        for i_episode in range(int(num_episodes / 10)):
            episode_return = 0
            state = env.reset()
            done = False
            while not done:
                action1 = agent.take_action(state[0])
                action2 = agent2.take_action(state[1])
                action3 = agent3.take_action(state[2])
                action = (action1,action2,action3,random.randint(0,4))
                next_state, reward, done, _ = env.step(action,2)
                replay_buffer.add(state[2], action[2], reward[2], next_state[2], done[2])
                done = all(done)
                state = next_state
                episode_return += sum(reward)
                if replay_buffer.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent3.update(transition_dict)
            return_list.append(episode_return)
            if (i_episode + 1) % 10 == 0:
                pbar.set_postfix({
                    'episode':
                    '%d' % (num_episodes / 10 * i + i_episode + 1),
                    'return':
                    '%.3f' % np.mean(return_list[-10:])
                })
            pbar.update(1)
    env.render()

#将训练得到的agent保存到文件中
torch.save(agent3.q_net.state_dict(), 'dqn_agent3.pth')

#绘制训练过程中的回报曲线
plt.figure()
plt.plot(return_list)
plt.xlabel('Episode')
plt.ylabel('Return')
plt.show()

#计算平均回报
return_list = np.array(return_list).reshape(-1, 10)
average_return = np.mean(return_list, axis=1)
print('Average return:', average_return)
print('Average return over the last 10 episodes:',
      np.mean(average_return[-10:]))

agent4 = DQN(state_dim, hidden_dim, action_dim, lr, gamma, epsilon,
            target_update, device)
return_list = []

for i in range(10):
    with tqdm(total=int(num_episodes / 10), desc='Iteration %d' % i) as pbar:
        for i_episode in range(int(num_episodes / 10)):
            episode_return = 0
            state = env.reset()
            done = False
            while not done:
                action1 = agent.take_action(state[0])
                action2 = agent2.take_action(state[1])
                action3 = agent3.take_action(state[2])
                action4 = agent4.take_action(state[3])
                action = (action1,action2,action3,action4)
                next_state, reward, done, _ = env.step(action,3)
                replay_buffer.add(state[3], action[3], reward[3], next_state[3], done[3])
                done = all(done)
                state = next_state
                episode_return += sum(reward)
                if replay_buffer.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent4.update(transition_dict)
            return_list.append(episode_return)
            if (i_episode + 1) % 10 == 0:
                pbar.set_postfix({
                    'episode':
                    '%d' % (num_episodes / 10 * i + i_episode + 1),
                    'return':
                    '%.3f' % np.mean(return_list[-10:])
                })
            pbar.update(1)
    env.render()
        
#将训练得到的agent保存到文件中
torch.save(agent4.q_net.state_dict(), 'dqn_agent4.pth')

#绘制训练过程中的回报曲线
plt.figure()
plt.plot(return_list)
plt.xlabel('Episode')
plt.ylabel('Return')
plt.show()

#计算平均回报
return_list = np.array(return_list).reshape(-1, 10)
average_return = np.mean(return_list, axis=1)
print('Average return:', average_return)
print('Average return over the last 10 episodes:',
      np.mean(average_return[-10:]))

replay_buffer1 = ReplayBuffer(buffer_size)
replay_buffer2 = ReplayBuffer(buffer_size)
replay_buffer3 = ReplayBuffer(buffer_size)
replay_buffer4 = ReplayBuffer(buffer_size)

return_list = []
for i in range(10):
    with tqdm(total=int(num_episodes / 10), desc='Iteration %d' % i) as pbar:
        for i_episode in range(int(num_episodes / 10)):
            episode_return = 0
            state = env.reset()
            # state = np.array(state)
            # state = state.reshape(1, -1)
            # print(state.shape)
            done = False
            while not done:
                # print(state)
                # exit(0)
                action1 = agent.take_action(state[0])
                action2 = agent2.take_action(state[1])
                action3 = agent3.take_action(state[2])
                action4 = agent4.take_action(state[3])
                action = (action1,action2,action3,action4)
                # print(action)
                next_state, reward, done, _ = env.step(action,3)
                
                # print(next_state)
                # exit(0)
                # next_state = np.array(next_state)
                # next_state = next_state.reshape(1, -1)
                replay_buffer1.add(state[0], action[0], sum(reward), next_state[0], done[0])
                replay_buffer2.add(state[1], action[1], sum(reward), next_state[1], done[1])
                replay_buffer3.add(state[2], action[2], sum(reward), next_state[2], done[2])
                replay_buffer4.add(state[3], action[3], sum(reward), next_state[3], done[3])
                done = all(done)
                state = next_state
                episode_return += sum(reward)
                # 当buffer数据的数量超过一定值后,才进行Q网络训练
                if replay_buffer1.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer1.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent.update(transition_dict)
                if replay_buffer2.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer2.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent2.update(transition_dict)
                if replay_buffer3.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer3.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent3.update(transition_dict)
                if replay_buffer4.size() > minimal_size:
                    b_s, b_a, b_r, b_ns, b_d = replay_buffer4.sample(batch_size)
                    transition_dict = {
                        'states': b_s,
                        'actions': b_a,
                        'next_states': b_ns,
                        'rewards': b_r,
                        'dones': b_d
                    }
                    agent4.update(transition_dict)
                
            return_list.append(episode_return)
            if (i_episode + 1) % 10 == 0:
                pbar.set_postfix({
                    'episode':
                    '%d' % (num_episodes / 10 * i + i_episode + 1),
                    'return':
                    '%.3f' % np.mean(return_list[-10:])
                })
            pbar.update(1)
    env.render()


#绘制训练过程中的回报曲线
plt.figure()
plt.plot(return_list)
plt.xlabel('Episode')
plt.ylabel('Return')
plt.show()

#计算平均回报
return_list = np.array(return_list).reshape(-1, 10)
average_return = np.mean(return_list, axis=1)
print('Average return:', average_return)
print('Average return over the last 10 episodes:',
      np.mean(average_return[-10:]))
