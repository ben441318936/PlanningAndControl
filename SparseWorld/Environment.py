from collections import namedtuple
from typing import List

import numpy as np

from MotionModels import MotionModel, DifferentialDrive

'''
For AABB (Axis-Aligned Bounding-Box) type obstacles.
'''
Obstacle = namedtuple("Obstacle", ["top", "left", "bottom", "right"])

'''
For ray-tracing.
If line segment intersects obstacle, collide = True, endpoint = point of intersection.
Else collide = False, endpoint = endpoint of the line segment
'''
RayTraceResult = namedtuple("RayTraceResult", ["collide", "endpoint"])

'''
For LIDAR scan results.
'''
ScanResult = namedtuple("ScanResult", ["angle", "range"])

class Environment():
    def __init__(self, env_size=(100,100), motion_model: MotionModel = None) -> None:
        self.env_size = env_size
        self._motion_model = motion_model
        self._agent_state = np.zeros((self._motion_model.state_dim))
        self.agent_position = np.array([env_size[0]/2, env_size[1]/2])
        self._obstacles = []

    def add_obstacle(self, obs: Obstacle) -> bool:
        if obs.left >= 0 and obs.right <= self.env_size[0] and obs.bottom >= 0 and obs.top <= self.env_size[1]:
            self._obstacles.append(obs)
            return True
        else:
            return False

    @property
    def agent_state(self) -> np.ndarray:
        return self._agent_state

    @agent_state.setter
    def agent_state(self, state: np.ndarray) -> bool:
        if len(state.shape) == 1 and state.shape[0] == self._motion_model.state_dim:
            self._agent_state = state
            return True
        else:
            return False
    
    @property
    def agent_position(self) -> np.ndarray:
        return self._motion_model.state_2_position(self._agent_state)

    @agent_position.setter
    def agent_position(self, position: np.ndarray) -> bool:
        if len(position.shape) == 1 and position.shape[0] == 2:
            self._agent_state[self._motion_model.position_state_idx()] = position
            return True
        else:
            return False

    @property
    def agent_heading(self) -> np.ndarray:
        return self._motion_model.state_2_heading(self._agent_state)

    @property
    def agent_yaw_rate(self) -> np.ndarray:
        return self._motion_model.state_2_yaw_rate(self._agent_state)

    @property
    def agent_velocity(self) -> np.ndarray:
        return self._motion_model.state_2_velocity(self._agent_state)

    def agent_take_step(self, input, braking=False) -> bool:
        new_state = self._motion_model.step(self._agent_state, input, braking)
        if not self.state_out_of_bounds(new_state) and not self.state_in_obstacles(new_state):
            self._agent_state = new_state
            return True
        else:
            return False

    def position_out_of_bounds(self, pos: np.ndarray) -> bool:
        return pos[0] < 0 or pos[0] > self.env_size[0] or pos[1] < 0 or pos[1] > self.env_size[1]

    def state_out_of_bounds(self, state: np.ndarray) -> bool:
        pos = self._motion_model.state_2_position(state)
        return self.position_out_of_bounds(pos)

    def position_in_obstacle(self, pos: np.ndarray, obs: Obstacle) -> bool:
        return pos[0] >= obs.left and pos[0] <= obs.right and pos[1] >= obs.bottom and pos[1] <= obs.top

    def state_in_obstacle(self, state: np.ndarray, obs: Obstacle) -> bool:
        pos = self._motion_model.state_2_position(state)
        return self.position_in_obstacle(pos, obs)
        
    def state_in_obstacles(self, state) -> bool:
        for obs in self._obstacles:
            if self.state_in_obstacle(state, obs):
                return True
        return False

    def ray_intersect_obstacle(self, ray: np.ndarray, obs: Obstacle) -> RayTraceResult:
        '''
        Core ray-tracing algorithm. Valid for AABB obstacle collision.
        '''

        p0 = ray[0,:]
        p1 = ray[1,:]
        d = p1-p0 # vector from p0 to p1

        if self.position_in_obstacle(p0, obs):
            return RayTraceResult(collide=False, endpoint=p0)
        
        # use the min and max representation for box, taken along each axis
        box = np.array([[obs.left, obs.bottom], [obs.right, obs.top]])

        tmin = -np.inf
        tmax = np.inf

        for i in range(p0.shape[0]): # this iterates through the coordinates, i.e x,y,z,...
            if (d[i] != 0):
                t1 = (box[0,i] - p0[i]) / d[i]
                t2 = (box[1,i] - p0[i]) / d[i]
                tmin = max(tmin, min(t1, t2))
                tmax = min(tmax, max(t1, t2))
            elif (p0[i] <= box[0,i] or p0[i] >= box[1,i]):
                return RayTraceResult(collide=False, endpoint=p1)

        if tmax > tmin and tmax > 0 and tmin < 1:
            return RayTraceResult(collide=True, endpoint=p0 + tmin * d)
        else:
            return RayTraceResult(collide=False, endpoint=p1)

    def ray_intersect_obstacles(self, ray: np.ndarray) -> List[np.ndarray]:
        int_points = []
        for obs in self._obstacles:
            result = self.ray_intersect_obstacle(ray, obs)
            if result.collide:
                int_points.append(result.endpoint)
        return int_points

    def scan_cone(self, angle_range: tuple = (0,2*np.pi), max_range=1, resolution=0.1) -> List[ScanResult]:
        '''
        0 radian is the heading of the agent.
        Output is a list of ScanResults (angle, range) measurements
        '''
        results = []
        angles = np.arange(angle_range[0], angle_range[1], resolution)
        cone_ends = np.array([max_range * np.cos(angles), max_range * np.sin(angles)]).T
        for i in range(angles.shape[0]):
            ray = np.array([self.agent_position, self.agent_position + cone_ends[i,:]])
            int_points = self.ray_intersect_obstacles(ray)
            if len(int_points) == 0:
                results.append(ScanResult(angles[i], max_range))
            else:
                int_points = np.array(int_points)
                ranges = np.linalg.norm(int_points - self.agent_position, axis=1)
                results.append(ScanResult(angles[i], np.amin(ranges)))
        return results


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    M = DifferentialDrive(sampling_period=0.1)
    E = Environment(motion_model=M)

    print(E.agent_position)

    E.add_obstacle(Obstacle(top=53,bottom=49,left=52,right=55))

    results = E.scan_cone(angle_range=(-np.pi/2, np.pi/2), max_range=5, resolution=0.05)

    plt.figure()
    for res in results:
        ang = res.angle
        rng = res.range
        start = E.agent_position
        end = start + rng * np.array([np.cos(ang), np.sin(ang)])
        plt.plot([start[0], end[0]], [start[1], end[1]])
        plt.axis("equal")
    plt.show()

    # pos = []
    # vel = []

    # for i in range(50):
    #     pos.append(E.get_agent_position())
    #     vel.append(E.get_agent_velocity())
    #     E.agent_take_step(input=np.array([0.1,0.5]))

    # pos = np.array(pos)
    # vel = np.array(vel)

    # plt.figure()
    # plt.subplot(1,2,1)
    # plt.plot(pos[:,0], pos[:,1])
    # plt.axis("equal")
    # plt.subplot(1,2,2)
    # plt.plot(vel)
    # plt.show()