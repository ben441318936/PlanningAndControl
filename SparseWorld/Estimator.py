'''
Implements different state estimation schemes.

Uses the python controls toolbox.

Implements an abstract Estimator class that defines the basic estimator interface.
Estimator objects should take in a MotionModel object, and use the MotionModel utilities
for state and parameter extraction.
'''

from abc import ABC, abstractmethod
import numpy as np
import control

from MotionModels import MotionModel, DifferentialDrive, DifferentialDriveVelocityInput

class Estimator(ABC):
    '''
    Defines basic interface for estimator objects.
    '''

    __slots__ = ("_motion_model", "_estimate_state")

    def __init__(self, motion_model: MotionModel) -> None:
        self._motion_model = motion_model

    # initialize the estimator
    def init_estimator(self, init_state: np.ndarray = None) -> None:
        if init_state is None:
            init_state = np.zeros((self._motion_model.state_dim, self._motion_model.state_dim))
        self._estimate_state = init_state

    # predict the next state using known input and motion model
    @abstractmethod
    def predict(self, control_input) -> None:
        pass

    # update the current state using latest observation
    @abstractmethod
    def update(self, observation) -> None:
        pass

    # extract the most probable state for control use
    @property
    def estimate(self) -> np.ndarray:
        pass

class WheelSpeedEstimator(Estimator):
    '''
    Stationary Kalman Filter for the wheel speeds using torque and encoder reading.
    '''

    __slots__ = ("_phi", "_L", "_QN", "_RN")

    def __init__(self, motion_model: DifferentialDrive, QN=np.eye(2), RN=np.eye(2)) -> None:
        super().__init__(motion_model)
        self._motion_model = motion_model
        self._QN = QN
        self._RN = RN
        self.compute_gain() # this sets self._L, the estimator gain
        self.init_estimator(np.array([0.0,0.0]))

    @property
    def QN(self) -> np.ndarray:
        return self._QN

    @property
    def RN(self) -> np.ndarray:
        return self._RN

    @property
    def L(self) -> np.ndarray:
        return self._L

    def compute_gain(self) -> None:
        # continuous time model params
        A = np.array([[-self._motion_model.parameters["wheel friction"], 0], 
                      [0, -self._motion_model.parameters["wheel friction"]]])
        B = np.array([[1/self._motion_model.parameters["inertia"], 0], 
                      [0, 1/self._motion_model.parameters["inertia"]]])
        C = np.eye(2)
        # convert to discrete time
        sys_c = control.ss(A, B, C, np.zeros((2,2)))
        sys_d = control.sample_system(sys_c, self._motion_model.sampling_period)
        # this lqe uses x_(t+1|t+1) = x_(t+1|t) + L @ (z - C x_(t+1|t))
        self._L, P, E = control.dlqe(sys_d, self._QN, self._RN)
        self._L = np.array(self._L)

    def predict(self, control_input) -> None:
        self._estimate_state = self._motion_model.torque_to_phi_step(self._estimate_state, control_input)

    def update(self, observation) -> None:
        self._estimate_state = self._estimate_state + self._L @ (observation - self._estimate_state)

    @property
    def estimate(self) -> np.ndarray:
        return self._estimate_state


if __name__ == "__main__":

    import matplotlib.pyplot as plt

    from Controller import PVelocitySSTorqueControl

    # create motion model
    M = DifferentialDrive(sampling_period=0.01)

    # create controller
    C = PVelocitySSTorqueControl(M)

    # create estimator
    E = WheelSpeedEstimator(M)
    curr_state = np.array([50,50,0,0,0])
    E.init_estimator(curr_state[3:5])

    goal_pos = np.array([60,60])

    real_speeds = [curr_state[3:5]]
    estimated_speeds = [curr_state[3:5]]

    for i in range(10000):
        input_torque = C.control(curr_state, goal_pos)
        curr_state = M.step(curr_state, input_torque)
        real_speeds.append(curr_state[3:5])

        E.predict(input_torque)
        E.update(curr_state[3:5])
        estimated_speeds.append(E.estimate)

    real_speeds = np.array(real_speeds)
    estimated_speeds = np.array(estimated_speeds)

    plt.figure()
    plt.subplot(2,2,1)
    plt.plot(real_speeds[:,0])
    plt.ylabel("phi_R")
    plt.subplot(2,2,2)
    plt.plot(real_speeds[:,1])
    plt.ylabel("phi_L")
    plt.subplot(2,2,3)
    plt.plot(estimated_speeds[:,0])
    plt.ylabel("e_phi_R")
    plt.subplot(2,2,4)
    plt.plot(estimated_speeds[:,1])
    plt.ylabel("e_phi_L")
    plt.tight_layout(pad=2)
    plt.show()

