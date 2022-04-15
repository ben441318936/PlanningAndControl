import numpy as np
from enum import IntEnum

class GridStatus(IntEnum):
    EMPTY = 0
    WALL = 1
    TARGET = 2
    AGENT = 3
    BOTH = 4
    PREV_AGENT = 5

class ScanStatus(IntEnum):
    OUT_OF_BOUNDS = -2
    OBSTRUCTED = -1
    EMPTY = GridStatus.EMPTY
    WALL = GridStatus.WALL
    TARGET = GridStatus.TARGET
    AGENT = GridStatus.AGENT
    BOTH = GridStatus.BOTH

class Direction(IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

DirectionDict = {
    (-1,0): Direction.UP,
    (1,0): Direction.DOWN,
    (0,-1): Direction.LEFT,
    (0,1): Direction.RIGHT,
}

class Grid(object):
    '''
    Grid that represents the environment.
    Core data structure is a 2D array.
    '''
    def __init__(self,grid_size) -> None:
        self._grid = np.zeros((grid_size),dtype=int)
        self.agent_pos = None
        self.target_pos = None

    def in_bounds(self,coord) -> bool:
        return coord[0] >= 0 and coord[0] < self._grid.shape[0] and coord[1] >= 0 and coord[1] < self._grid.shape[1]

    def not_wall(self,coord) -> bool:
        return self._grid[coord[0],coord[1]] != GridStatus.WALL

    def place_agent(self,row,col) -> bool:
        if self.in_bounds((row,col)) and self.not_wall((row,col)):
            if self.agent_pos is not None:
                self._grid[self.agent_pos[0], self.agent_pos[1]] = GridStatus.PREV_AGENT
            if self._grid[row,col] == GridStatus.TARGET:
                self._grid[row,col] = GridStatus.BOTH
            else:
                self._grid[row,col] = GridStatus.AGENT
            self.agent_pos = np.array([row,col])
            # in case we overwrote the target marker
            if self.target_pos is not None:
                self._grid[self.target_pos[0], self.target_pos[1]] = GridStatus.TARGET
            return True
        else:
            return False

    def place_target(self,row,col) -> None:
        if self.in_bounds((row,col)) and self.not_wall((row,col)):
            if self.target_pos is not None:
                self._grid[self.target_pos[0], self.target_pos[1]] = GridStatus.EMPTY
            if self._grid[row,col] == GridStatus.AGENT:
                self._grid[row,col] = GridStatus.BOTH
            else:
                self._grid[row,col] = GridStatus.TARGET
            self.target_pos = np.array([row,col])
            return True
        else:
            return False

    def agent_move(self,dir) -> bool:
        if dir == Direction.RIGHT: # right
            coord = self.agent_pos + np.array([0,1])
        elif dir == Direction.DOWN: # down
            coord = self.agent_pos + np.array([1,0])
        elif dir == Direction.LEFT: # left
            coord = self.agent_pos + np.array([0,-1])
        elif dir == Direction.UP: # up
            coord = self.agent_pos + np.array([-1,0])

        if self.in_bounds(coord) and self.not_wall(coord):
            return self.place_agent(coord[0], coord[1])
        else:
            return False

    def scan(self,area) -> list:
        '''
        Takes in a list of coordinate offsets, centered around the agent.
        Return the status of each coordinate.
        '''
        result = []
        for offset in area:
            coord = self.agent_pos + offset
            if not self.in_bounds(coord):
                result.append((offset, ScanStatus.OUT_OF_BOUNDS))
            elif self._grid[coord[0],coord[1]] == GridStatus.EMPTY or self._grid[coord[0],coord[1]] == GridStatus.AGENT or self._grid[coord[0],coord[1]] == GridStatus.PREV_AGENT:
                result.append((offset, ScanStatus.EMPTY))
            elif self._grid[coord[0],coord[1]] == GridStatus.WALL:
                result.append((offset, ScanStatus.WALL))
            elif self._grid[coord[0],coord[1]] == GridStatus.TARGET or self._grid[coord[0],coord[1]] == GridStatus.BOTH:
                result.append((offset, ScanStatus.TARGET))
        return result

    def relative_target_pos(self) -> None:
        '''
        Returns the position of the target relative to the agent.
        '''
        return self.target_pos - self.agent_pos

    def print_grid(self) -> None:
        for i in range(self._grid.shape[0]):
            print(self._grid[i])


if __name__ == "__main__":
    G = Grid((10,10))
    print("Initialization")
    G.print_grid()
    G.place_agent(3,3)
    G.place_target(2,2)
    print("After placement")
    G.print_grid()
    G.agent_move(Direction.UP)
    print("After agent move")
    G.print_grid()