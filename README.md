TimeShift - mass timestamp shifter
==================================

TimeShift deals with the task of updating all time stamps in the
file with relative offset, thus making an impression certain logged
sequence of events took place at different time interval.

Such desire may arise when dealing with event logs, timestamped in
local time, or to cover up for bugs in importing software that messes
up conversion of local timestamps to UTC for various reasons.

The reverse situation also happens: some software prefers to
interpret all time stamps as of they were made in local time, making
an unnecessary conversion to UTC when source is already in UTC. We
need to shift those into local time before moving forward.

For example, you can shift the following:
* IM logs
* server logs
* GPS tracks

## Usage
To get comprehensive usage help, run `timeshift.py --help` and
`timeshift.py --long-help`