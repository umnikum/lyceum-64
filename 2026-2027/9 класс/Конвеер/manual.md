# RoboticArm.txt — Driver Manual

## File basics
- One command per line.
- Lines starting with `#` (or everything after `#`) are comments.
- Empty lines are ignored.
- The arm loads the file at startup. If the file is missing, a sample is created.
- When the last command finishes, the program loops from the top.

## Joint commands (relative)
R1 25          # add +25° to current R1 target
R2 -40         # add -40° to current R2 target
R3 30 CC       # force counterclockwise: treat 30 as -30
R4 15
R5 0
| Joint | Role              | Limits (hard)   | Notes                          |
|-------|-------------------|-----------------|--------------------------------|
| R1    | Base rotation     | none            | Full 360°                      |
| R2    | Elbow 1           | 5° … 175°       | Cannot go fully straight/back  |
| R3    | Elbow 2           | 5° … 175°       | Same as R2                     |
| R4    | Wrist fold        | 185° … 355°     | Folded range                   |
| R5    | Handle spin       | none            | Only rotates the gripper       |

- Commands are **relative** to the angle at the moment the line is executed.
- Intermediate joints (R2–R4) are clamped to the limits above after each step.
- Motion speed is fixed (`max_speed ≈ 2.6 °/frame`).

## Sensors
| ID  | Type / location                                      |
|-----|------------------------------------------------------|
| D0  | Distance sensor on the hand, pointing at the bottom  |
| D1  | Fixed, left of arm, looking down toward belt         |
| D2  | Fixed, left of arm, looking up from below belt       |
| D3  | Fixed, right of arm, looking down toward belt        |
| D4  | Fixed, right of arm, looking up from below belt      |

- Reading is distance in pixels (or `9999` if nothing is in range).
- Typical useful range: roughly 0–130.

## WAIT conditions
WAIT D0 '<' 40
WAIT D1 '<' 80 OR D2 '<' 80
WAIT D1 '>' 130 AND D3 '>' 130
WAIT NOT D0 '<' 25
- Supports: `<` `>` `AND` `OR` `NOT` and parentheses.
- The arm pauses on a `WAIT` until the expression becomes true, then continues.

## Belt control
STOP      # freeze the conveyor
RESUME    # start the conveyor again

## Tips
- Keep intermediate joint moves modest so the arm stays within limits.
- Use `D0 < N` (small N) to detect contact / proximity under the hand.
- Test one joint at a time while paused if the pose looks wrong.
- Delete `RoboticArm.txt` and restart to regenerate the sample file.
