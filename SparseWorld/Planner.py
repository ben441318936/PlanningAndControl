'''
Implements different planning algorithms.
'''

from abc import ABC, abstractmethod
from sre_constants import RANGE_UNI_IGNORE
import numpy as np
from typing import List

from Environment import ScanResult
from Map import Map, GridStatus, GridMap, OccupancyGrid, raytrace

from pqdict import pqdict

from collections import namedtuple

from functools import partial


class Planner(ABC):
    '''
    Basic planner interface.
    '''

    __slots__ = ("_path", "_path_idx")

    def __init__(self) -> None:
        self._path = None
        self._path_idx = None

    @property
    def path(self) -> np.ndarray:
        if self._path is None:
            return np.array([])
        else:
            return self._path

    def path_valid(self) -> bool:
        '''
        Check if current planned path is still valid according to what we know.
        '''
        if self._path is None:
            # doesn't have a path yet
            return False
        return True

    @abstractmethod
    def plan(self, start: np.ndarray, target: np.ndarray) -> bool:
        '''
        Implements high level planning logic.
        '''
        pass

    @abstractmethod
    def _plan_algo(self, start: np.ndarray, target: np.ndarray) -> bool:
        '''
        Implements the actual planning algorithm.
        '''
        pass

    def next_stop(self) -> np.ndarray:
        '''
        Return the next stop in the planned path.
        '''
        return self._path[self._path_idx+1]

    def take_next_stop(self) -> np.ndarray:
        '''
        Return the next stop, then advance the path idx.
        '''
        next_pos = self._path[self._path_idx+1]
        self._path_idx += 1
        return next_pos

    @abstractmethod
    def update_environment(self, scan_start: np.ndarray, scan_results: List[ScanResult]) -> None:
        '''
        Updates the planner's version of the environment.
        Could be updating a map or a list of obstacles/landmarks.
        '''
        pass

VertexInfo = namedtuple("VertexInfo", ["coord", "cost"])

def get_8_neighbors(map: np.ndarray, vertex: tuple) -> List[VertexInfo]:
    infos = []
    for i in range(-1,2):
        for j in range(-1,2):
            pos = np.array(vertex) + np.array([i,j])
            if (not (i == 0 and j == 0)) and pos[0] >= 0 and pos[1] >= 0 and pos[0] < map.shape[0] and pos[1] < map.shape[1]:
                if map[vertex] != GridStatus.OBSTACLE and map[pos[0], pos[1]] != GridStatus.OBSTACLE:
                    cost = np.linalg.norm(np.array([i,j]))
                else:
                    cost = np.inf
                coord = tuple(pos)
                infos.append(VertexInfo(coord, cost))
    return infos

def get_n_grid_neighbors(map: np.ndarray, vertex: tuple, n: int = 3) -> List[VertexInfo]:
    '''
    Get neighbors in a n x n grid. Using a binary map.

    n should be an odd interger greater than or equal to 3.

    Ex: n=3, get the 8 neighbors in a 3x3 grid.
    '''
    if n < 3:
        n = 3
    if n % 2 == 0:
        n += 1
    infos = []
    for i in range(-(n-1)//2,(n-1)//2+1):
        for j in range(-(n-1)//2,(n-1)//2+1):
            pos = np.array(vertex) + np.array([i,j])
            if (not (i == 0 and j == 0)) and pos[0] >= 0 and pos[1] >= 0 and pos[0] < map.shape[0] and pos[1] < map.shape[1]:
                ray_xx, ray_yy = raytrace(vertex[0], vertex[1], pos[0], pos[1])
                if np.sum(map[ray_xx, ray_yy] == GridStatus.OBSTACLE) == 0:
                    cost = np.linalg.norm(np.array([i,j]))
                else:
                    cost = np.inf
                coord = tuple(pos)
                infos.append(VertexInfo(coord, cost))
    return infos
    

class SearchBasedPlanner(Planner):
    '''
    Planner based on discretizing the environment and searching the resulting graph.
    '''
    __slots__ = ("_map", "_neighbor_func")

    def __init__(self, xlim=(0,100), ylim=(0,100), res=1, neighbor_func=get_n_grid_neighbors) -> None:
        super().__init__()
        self._map = OccupancyGrid(xlim=xlim, ylim=ylim, res=res)
        self._neighbor_func = neighbor_func

    @property
    def map(self) -> OccupancyGrid:
        return self._map

    def update_environment(self, scan_start: np.ndarray, scan_results: List[ScanResult]) -> None:
        return self._map.update_map(scan_start, scan_results)

    def next_stop(self) -> np.ndarray:
        return self._map.convert_to_world_coord(super().next_stop())

    def take_next_stop(self) -> np.ndarray:
        return self._map.convert_to_world_coord(super().take_next_stop())

    def path_valid(self, start: np.ndarray) -> bool:
        if super().path_valid():
            # self._path.shape[0] == 1 iff start and stop is the same in the planning algo
            if self._path.shape[0] != 1 and self._path_idx+1 >= len(self._path):
                # no more stops in current path
                return False
            # path is longer than 1, check straight line between each stop
            else:
                for i in range(self._path_idx, len(self._path)):
                    if i == 0:
                        start = self._map.convert_to_grid_coord(start)
                    else:
                        start = self._path[i-1]
                    pos = self._path[i]
                    ray_xx, ray_yy = raytrace(start[0], start[1], pos[0], pos[1])
                    if np.sum(self._map._map[ray_xx, ray_yy] > 0) == 0:
                        return False
            return True
        else:
            return False


class A_Star_Planner(SearchBasedPlanner):
    '''
    Planner than implements weighted A*.
    '''

    __slots__ = ("_eps", "_heuristic")

    def __init__(self, xlim=(0,100), ylim=(0,100), res=1, neighbor_func=get_n_grid_neighbors, eps=1, heuristic=np.linalg.norm) -> None:
        super().__init__(xlim=xlim, ylim=ylim, res=res, neighbor_func=neighbor_func)
        self._eps = eps
        self._heuristic = heuristic

    def _plan_algo(self, start: np.ndarray, target: np.ndarray) -> bool:
        if start[0] == target[0] and start[1] == target[1]:
            self._path = np.array([start])
            return True

        binary_map = self._map.get_binary_map()
        # Initialize the data structures
        # Labels
        g = np.ones(binary_map.shape) * np.inf
        start_ind = tuple(start)
        goal_ind = tuple(target)
        g[start_ind] = 0
        # Priority queue for OPEN list
        OPEN = pqdict({})
        OPEN[start_ind] = g[start_ind] + self._eps * self._heuristic(start - target)
        # Predecessor matrix to keep track of path
        # # create dtype string
        # dtype_string = ",".join(['i' for _ in range(len(map.shape))])
        # pred = np.full(map.shape, -1, dtype=dtype_string)
        pred = np.full((binary_map.shape[0], binary_map.shape[1], 2), -1, dtype=int)

        done = False

        while not done:
            if len(OPEN) != 0 :
                parent_ind = OPEN.popitem()[0]
            else:
                break
            if parent_ind[0] == goal_ind[0] and parent_ind[1] == goal_ind[1]:
                done = True
                break
            # get neighbors
            infos = self._neighbor_func(binary_map, parent_ind)
            # # Get list of children
            # children_inds = self._get_neighbors_inds(parent_ind)
            # # Get list of costs from parent to children
            # children_costs = self._get_parent_children_costs(parent_ind)
            for child in infos:
                child_ind = child.coord
                child_cost = child.cost
                if g[child_ind] > g[parent_ind] + child_cost:
                    g[child_ind] = g[parent_ind] + child_cost
                    pred[child_ind[0], child_ind[1], :] = np.array(parent_ind)
                    # This updates if child already in OPEN
                    # and appends to OPEN otherwise
                    OPEN[child_ind] = g[child_ind] + self._eps * self._heuristic(np.array(child_ind) - target)

        # We have found a path
        path = []
        if done:
            pos = target
            while True:
                path.append(pos)
                if pos[0] == start[0] and pos[1] == start[1]:
                    break
                else:
                    pos = pred[pos[0], pos[1], :]
        path = list(reversed(path))
        self._path = np.array(path)
        return done

    def plan(self, start: np.ndarray, target: np.ndarray) -> bool:
        start = self._map.convert_to_grid_coord(start)
        target = self._map.convert_to_grid_coord(target)
        if self._plan_algo(start, target):
            self._path_idx = 0
            return True
        else:
            print("Planning failed with discrete cells")
            print("Start:", start)
            print("Target:", target)
        return False

    def next_stop(self) -> np.ndarray:
        if self._path.shape[0] == 1:
            self._path_idx = -1    
        return super().next_stop()
    
    def take_next_stop(self) -> np.ndarray:
        if self._path.shape[0] == 1:
            self._path_idx = -1
        return super().take_next_stop()
    

    
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    from MotionModel import DifferentialDriveTorqueInput
    from Environment import Environment, Obstacle

    M = DifferentialDriveTorqueInput(sampling_period=0.1)
    E = Environment(motion_model=M, target_position=np.array([90,50]))

    E.agent_heading = 0

    # E.add_obstacle(Obstacle(top=60,bottom=52,left=52,right=60))
    # E.add_obstacle(Obstacle(top=48,bottom=40,left=52,right=60))

    E.add_obstacle(Obstacle(top=60,left=53,bottom=40,right=70))

    # MAP = OccupancyGrid(xlim=(0,100), ylim=(0,100), res=1)
    P = A_Star_Planner(xlim=(0,100), ylim=(0,100), res=1, neighbor_func=partial(get_n_grid_neighbors, n=3))

    results = E.scan_cone(angle_range=(-np.pi/2, np.pi/2), max_range=5, resolution=1/180*np.pi)
    P.update_environment(E.agent_position, results)

    P.plan(E.agent_position, E.target_position)

    plt.figure()
    plt.plot(P.path[:,0], P.path[:,1])
    plt.show()