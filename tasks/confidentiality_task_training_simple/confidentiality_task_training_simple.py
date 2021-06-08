"""
Main config file for the convidentiality task training stage 2a - simple discrimination
This behavior config file makes use of three 
Bpod classes the main Bpod and the StateMachine aswell as the RotaryEncoder.

In addition it uses three custom classes:
    Stimulus: handeling the psychopy configuration and drawing of the stimulus on the screens
    ProbabilityConstructor: generating the necessary probabilites for each trial
    BpodRotaryEncoder: handeling the rotary encoder and reading the position
    TrialParameterHandler: generating the necessary parameters for each session from the user input and predefined parameters

"""



import threading
import os,sys,inspect
import json
import random
import time

# import pybpod modules
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodgui_api.models.session import Session

# span subprocess
# add module path to sys path
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
maxland_root = os.path.dirname(os.path.dirname(currentdir))
modules_dir = os.path.join(maxland_root,"modules")
sys.path.insert(0,modules_dir) 

# import custom modules
from stimulus_conf import Stimulus
#from probability_conf import ProbabilityConstuctor
from rotaryencoder import BpodRotaryEncoder
from parameter_handler import TrialParameterHandler
from userinput import UserInput

# import usersettings
import usersettings

# create settings object
session_folder = os.getcwd()
# TODO: correct for final foderl
#settings_folder = os.path.join(session_folder.split('experiments')[0],"tasks","confidentiality_task_training_simple")
settings_folder = session_folder
global settings_obj
settings_obj = TrialParameterHandler(usersettings, settings_folder, session_folder,"conf")

# create bpod object
bpod=Bpod('COM6')

# create tkinter userinput dialoge window
# TODO: fix for windows
window = UserInput(settings_obj)
window.draw_window_bevore_conf()
window.show_window()


#settings_obj.run_session = True

# create multiprocessing variabls
# flags
display_stim_event = threading.Event()
still_show_event = threading.Event()
display_stim_event.clear()
still_show_event.clear()
# set functions


# run session
if settings_obj.run_session:
    settings_obj.update_userinput_file_conf()
    # rotary encoder config
    # enable thresholds
    rotary_encoder_module = BpodRotaryEncoder('COM4', settings_obj, bpod)
    rotary_encoder_module.load_message()
    rotary_encoder_module.configure()
    #rotary_encoder_module.enable_stream()

    # softcode handler
    def softcode_handler(data):
        global run_closed_loop
        global run_open_loop
        if data == settings_obj.SC_PRESENT_STIM:
            display_stim_event.set()
            print("PRESENT STIMULUS")
        elif data == settings_obj.SC_START_OPEN_LOOP:
            stimulus_game.stop_closed_loop()
            print("START OPEN LOOP")
        elif data == settings_obj.SC_STOP_OPEN_LOOP:
            stimulus_game.stop_open_loop()
            print("stop open loop")
        elif data == settings_obj.SC_END_PRESENT_STIM:
            still_show_event.set()
            print("end present stim")
        elif data == settings_obj.SC_START_LOGGING:
            rotary_encoder_module.rotary_encoder.enable_logging()
        elif data == settings_obj.SC_END_LOGGING:
            rotary_encoder_module.rotary_encoder.disable_logging()
            print("disable logging")

    bpod.softcode_handler_function = softcode_handler

    #probability constructor
    global correct_stim_side
    correct_stim_side = {
        "right" : True, # True = correct
        "left" : False  # False = wrong
    }
    def get_random_side():
        global correct_stim_side
        random_side = bool(random.getrandbits(1))
        correct_stim_side["right"]=random_side
        correct_stim_side["left"]= not(random_side)

    #stimulus
    stimulus_game = Stimulus(settings_obj, rotary_encoder_module, correct_stim_side)
    sides_li = []
    # times
    times_li = []
    

    # create main state machine aka trial loop ====================================================================
    # state machine configs
    for trial in range(10):#range(settings_obj.trial_number):
        # create random stimulus side
        random_side = bool(random.getrandbits(1))
        correct_stim_side["right"]=random_side
        correct_stim_side["left"]= not(random_side)
        print(correct_stim_side)
        sides_li.append(correct_stim_side.copy())
        # get random punish time
        punish_time = round(random.uniform(
            settings_obj.time_dict['time_range_open_loop_fail_punish'][0],
            settings_obj.time_dict['time_range_open_loop_fail_punish'][1]
            ),2)
        times_li.append(punish_time)
        # construct states
        sma = StateMachine(bpod)
        # start state to define block of trial
        sma.add_state(
            state_name="start",
            state_timer=settings_obj.time_dict["time_start"],
            state_change_conditions={"Tup": "reset_rotary_encoder_wheel_stopping_check"},
            output_actions=[("SoftCode", settings_obj.SC_START_LOGGING)],
        )
        # reset rotary encoder bevore checking for wheel not stoping
        sma.add_state(
            state_name="reset_rotary_encoder_wheel_stopping_check",
            state_timer=0,
            state_change_conditions={"Tup":"wheel_stopping_check"},
            output_actions=[("Serial1", settings_obj.RESET_ROTARY_ENCODER)], # activate white light while waiting
        )

        # wheel stoping check ===========================================================
        #wheel not stoping check 
        sma.add_state(
            state_name="wheel_stopping_check",
            state_timer=5,#settings_obj.time_dict["time_wheel_stopping_check"],
            state_change_conditions={
                    "Tup":"present_stim",
                    settings_obj.THRESH_LEFT:"wheel_stopping_check_failed_punish",
                    settings_obj.THRESH_RIGHT:"wheel_stopping_check_failed_punish",
                    },
            output_actions=[],
        )
        sma.add_state(
            state_name="wheel_stopping_check_failed_punish",
            state_timer=settings_obj.time_dict["time_wheel_stopping_punish"],
            state_change_conditions={"Tup":"reset_rotary_encoder_wheel_stopping_check"},
            output_actions=[]
        )

        # Open Loop =====================================================================
        # continue if wheel stopped for time x
        sma.add_state(
            state_name="present_stim",
            state_timer=settings_obj.time_dict["time_stim_pres"],
            state_change_conditions={"Tup": "reset_rotary_encoder_open_loop"},
            output_actions=[("SoftCode", settings_obj.SC_PRESENT_STIM)],#after wait -> present initial stimulus
        )
        # reset rotary encoder bevor open loop starts
        sma.add_state(
            state_name="reset_rotary_encoder_open_loop",
            state_timer=0,
            state_change_conditions={"Tup": "open_loop"},
            output_actions=[("Serial1", settings_obj.RESET_ROTARY_ENCODER)], # reset rotary encoder postition to 0
        )

        # open loop detection
        sma.add_state(
            state_name="open_loop",
            state_timer=settings_obj.time_dict["time_open_loop"],
            state_change_conditions={
                "Tup": "stop_open_loop_fail",
                settings_obj.STIMULUS_LEFT: "stop_open_loop_reward_left",
                settings_obj.STIMULUS_RIGHT: "stop_open_loop_reward_right",
                },
            output_actions=[("SoftCode", settings_obj.SC_START_OPEN_LOOP)], # softcode to start open loop
        )

        # stop open loop fail
        sma.add_state(
            state_name="stop_open_loop_fail",
            state_timer=0,
            state_change_conditions={"Tup": "open_loop_fail_punish"},
            output_actions=[("SoftCode", settings_obj.SC_STOP_OPEN_LOOP)] # stop open loop in py game
        )
        # open loop fail punish time & exit trial
        sma.add_state(
            state_name="open_loop_fail_punish",
            state_timer=punish_time,
            state_change_conditions={"Tup": "inter_trial"},
            output_actions=[("SoftCode", settings_obj.SC_END_PRESENT_STIM)]
        )

        #=========================================================================================
        # reward left
        sma.add_state(
            state_name="stop_open_loop_reward_left",
            state_timer=settings_obj.time_dict["time_stim_freez"],
            state_change_conditions={"Tup": "check_reward_left"},
            output_actions=[("SoftCode", settings_obj.SC_STOP_OPEN_LOOP)] # stop open loop in py game
        )

        # check for reward: 
        if correct_stim_side["left"]:
            print("reward_left")
            sma.add_state(
                state_name="check_reward_left",
                state_timer=0,
                state_change_conditions={"Tup": "reward_left"},
                output_actions=[]
            )
            sma.add_state(
                state_name="reward_left",
                state_timer=settings_obj.time_dict["open_time_reward"],
                state_change_conditions={"Tup": "reward_left_waiting"},
                output_actions=[("SoftCode", settings_obj.SC_END_PRESENT_STIM),
                                ("Valve1", 255)
                                ]
            )
            sma.add_state(
                state_name="reward_left_waiting",
                state_timer=settings_obj.time_dict["time_reward_waiting"],
                state_change_conditions={"Tup": "inter_trial"},
                output_actions=[]
            )
        else:
            print("noreward_left")
            # no reward
            sma.add_state(
                    state_name="check_reward_left",
                    state_timer=0,
                    state_change_conditions={"Tup": "no_reward_left"},
                    output_actions=[]
                )
            sma.add_state(
                state_name="no_reward_left",
                state_timer=0,
                state_change_conditions={"Tup": "reward_left_waiting"},
                output_actions=[("SoftCode", settings_obj.SC_END_PRESENT_STIM)]
            )
            sma.add_state(
                state_name="reward_left_waiting",
                # TODO: test random time
                state_timer=settings_obj.time_dict["time_noreward"],
                state_change_conditions={"Tup": "inter_trial"},
                output_actions=[]
            )

        #=========================================================================================
        # reward right
        sma.add_state(
            state_name="stop_open_loop_reward_right",
            state_timer=settings_obj.time_dict["time_stim_freez"],
            state_change_conditions={"Tup": "check_reward_right"},
            output_actions=[("SoftCode", settings_obj.SC_STOP_OPEN_LOOP)] # stop open loop in py game
        )

        # check for reward: 
        if correct_stim_side["right"]:
            print("reward_right")
            sma.add_state(
                state_name="check_reward_right",
                state_timer=0,
                state_change_conditions={"Tup": "reward_right"},
                output_actions=[]
            )
            sma.add_state(
                state_name="reward_right",
                state_timer=settings_obj.time_dict["open_time_reward"],
                state_change_conditions={"Tup": "reward_right_waiting"},
                output_actions=[("SoftCode", settings_obj.SC_END_PRESENT_STIM),
                                ("Valve1", 255)
                                ]
            )
            sma.add_state(
                state_name="reward_right_waiting",
                state_timer=settings_obj.time_dict["time_reward_waiting"],
                state_change_conditions={"Tup": "inter_trial"},
                output_actions=[]
            )
        else:
            print("noreward_right")
            # no reward
            sma.add_state(
                    state_name="check_reward_right",
                    state_timer=0,
                    state_change_conditions={"Tup": "no_reward_right"},
                    output_actions=[]
                )
            sma.add_state(
                state_name="no_reward_right",
                state_timer=0,
                state_change_conditions={"Tup": "reward_right_waiting"},
                output_actions=[("SoftCode", settings_obj.SC_END_PRESENT_STIM)]
            )
            sma.add_state(
                state_name="reward_right_waiting",
                # TODO: test random time
                state_timer=settings_obj.time_dict["time_noreward"],
                state_change_conditions={"Tup": "inter_trial"},
                output_actions=[]
            )

        # inter trial cleanup ===========================================================
        # inter trial time
        sma.add_state(
            state_name="inter_trial",
            state_timer=settings_obj.time_dict["time_inter_trial"],
            state_change_conditions={"Tup": "end_state"},
            output_actions=[],
        )

        # end state
        sma.add_state(
            state_name="end_state",
            state_timer=0,
            state_change_conditions={"Tup":"exit"},
            output_actions=[("SoftCode", settings_obj.SC_END_LOGGING)],
        )



        # send & run state machine
        bpod.send_state_machine(sma)
        pa = threading.Thread(target=bpod.run_state_machine, args=(sma,))
        pa.start()

        # run stimulus game
        stimulus_game.run_game(display_stim_event, still_show_event)

        # wiat until state machine finished
        #if not bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
        #    break
        pa.join() 
        
        # post trial cleanup
        print("---------------------------------------------------")
        print(f"trial: {trial}")

    #=========================================================================================================
    print("finished")

    # user input after session
    #window = UserInput(settings_obj)
    #window.draw_window_after()
    #window.show_window()

    # save session settings
    session_name = bpod.session_name
    # add sides_li & time_li to settings_obj
    settings_obj.sides_li = sides_li
    settings_obj.times_li = times_li
    # save usersettings of session
    settings_obj.save_usersettings(session_name)
    # save wheel movement of session
    rotary_encoder_module.rotary_encoder.disable_logging()
    # append wheel postition
    #log = rotary_encoder_module.get_logging()
    #print(log)
    #settings_obj.update_wheel_log(rotary_encoder_module.get_logging())
    # append stimulus postition
    #settings_obj.update_stim_log(stimulus_game.stimulus_posititon)
    #settings_obj.save_wheel_movement(session_name)
    # save stimulus postition of session
    #settings_obj.save_stimulus_postition(session_name)

    # push session to alyx


    #print(len(rotary_encoder_module.rotary_encoder.get_logged_data()))

# remove session from pybpod if not run_loop
else:
    #todo donst save current session
    None

rotary_encoder_module.close()
bpod.close()

