from sebastian.core import MIDI_PITCH, OFFSET_64, DURATION_64
from sebastian.core import Point, OSequence

from sebastian.core.notes import modifiers, letter
from functools import wraps, partial


def transform_sequence(f):
    """
    A decorator to take a function operating on a point and
    turn it into a function returning a callable operating on a sequence.
    The functions passed to this decorator must define a kwarg called "point",
    or have point be the last positional argument
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        #The arguments here are the arguments passed to the transform,
        #ie, there will be no "point" argument

        #Send a function to seq.map_points with all of its arguments applied except
        #point
        return lambda seq: seq.map_points(partial(f, *args, **kwargs))

    return wrapper


@transform_sequence
def add(properties, point):
    point.update(properties)
    return point


@transform_sequence
def degree_in_key(key, point):
    degree = point["degree"]
    pitch = key.degree_to_pitch(degree)
    point["pitch"] = pitch
    return point


@transform_sequence
def degree_in_key_with_octave(key, base_octave, point):
    degree = point["degree"]
    pitch, octave = key.degree_to_pitch_and_octave(degree)
    point["pitch"] = pitch
    point["octave"] = octave + base_octave
    return point


@transform_sequence
def transpose(semitones, point):
    if MIDI_PITCH in point:
        point[MIDI_PITCH] = point[MIDI_PITCH] + semitones
    return point


@transform_sequence
def stretch(multiplier, point):
    point[OFFSET_64] = int(point[OFFSET_64] * multiplier)
    if DURATION_64 in point:
        point[DURATION_64] = int(point[DURATION_64] * multiplier)
    return point


@transform_sequence
def invert(midi_pitch_pivot, point):
    if MIDI_PITCH in point:
        interval = point[MIDI_PITCH] - midi_pitch_pivot
        point[MIDI_PITCH] = midi_pitch_pivot - interval
    return point


def reverse():
    def _(sequence):
        new_elements = []
        last_offset = sequence.next_offset()
        if sequence and sequence[0][OFFSET_64] != 0:
            old_sequence = OSequence([Point({OFFSET_64: 0})]) + sequence
        else:
            old_sequence = sequence
        for point in old_sequence:
            new_point = Point(point)
            new_point[OFFSET_64] = last_offset - new_point[OFFSET_64] - new_point.get(DURATION_64, 0)
            if new_point != {OFFSET_64: 0}:
                new_elements.append(new_point)
        return OSequence(sorted(new_elements, key=lambda x: x[OFFSET_64]))
    return _


@transform_sequence
def midi_pitch(point):
    octave = point["octave"]
    pitch = point["pitch"]
    midi_pitch = [2, 9, 4, 11, 5, 0, 7][pitch % 7]
    midi_pitch += modifiers(pitch)
    midi_pitch += 12 * octave
    point[MIDI_PITCH] = midi_pitch
    return point


@transform_sequence
def lilypond(point):
    if "lilypond" not in point:
        octave = point["octave"]
        pitch = point["pitch"]
        duration = point[DURATION_64]
        if octave > 4:
            octave_string = "'" * (octave - 4)
        elif octave < 4:
            octave_string = "," * (4 - octave)
        else:
            octave_string = ""
        m = modifiers(pitch)
        if m > 0:
            modifier_string = "is" * m
        elif m < 0:
            modifier_string = "es" * m
        else:
            modifier_string = ""
        pitch_string = letter(pitch).lower() + modifier_string
        duration_string = str(int(64 / duration))  # @@@ doesn't handle dotted notes yet
        point["lilypond"] = "%s%s%s" % (pitch_string, octave_string, duration_string)
    return point

_dynamic_markers_to_velocity = {
    'pppppp': 10,
    'ppppp': 16,
    'pppp': 20,
    'ppp': 24,
    'pp': 36,
    'p': 48,
    'mp': 64,
    'mf': 74,
    'f': 84,
    'ff': 94,
    'fff': 114,
    'ffff': 127,
}


def dynamics(start, end=None):
    """
    Apply dynamics to a sequence. If end is specified, it will crescendo or diminuendo linearly from start to end dynamics.

    You can pass dynamic markers as a strings or as midi velocity integers to this function.

    Example usage:

        s1 | dynamics('p')  # play a sequence in piano
        s2 | dynamics('p', 'ff')  # crescendo from p to ff
        s3 | dynamics('ff', 'p')  # diminuendo from ff to p

    Valid dynamic markers are %s
    """ % (_dynamic_markers_to_velocity.keys())
    def _(sequence):
        if isinstance(start, int):
            start_velocity = start
        elif start in _dynamic_markers_to_velocity:
            start_velocity = _dynamic_markers_to_velocity[start]
        else:
            raise ValueError("Unknown start dynamic: %s, must be in %s" % (start, _dynamic_markers_to_velocity.keys()))

        if end is None:
            end_velocity = start_velocity
        elif isinstance(end, int):
            end_velocity = end
        elif end in _dynamic_markers_to_velocity:
            end_velocity = _dynamic_markers_to_velocity[end]
        else:
            raise ValueError("Unknown end dynamic: %s, must be in %s" % (start, _dynamic_markers_to_velocity.keys()))

        retval = sequence.__class__([Point(point) for point in sequence._elements])

        if not len(retval):
            return retval  # causes div by zero if we don't exit early

        velocity_interval = (float(end_velocity) - float(start_velocity)) / (len(sequence) - 1)
        velocities = [int(start_velocity + velocity_interval * pos) for pos in range(len(sequence))]

        for point, velocity in zip(retval, velocities):
            point['velocity'] = velocity

        return retval
    return _
