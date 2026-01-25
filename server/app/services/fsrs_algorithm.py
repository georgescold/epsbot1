"""
FSRS (Free Spaced Repetition Scheduler) Algorithm Implementation
Based on Anki's modern FSRS algorithm (https://github.com/open-spaced-repetition)

This is a Python implementation of the FSRS-4.5 algorithm that optimizes
spaced repetition for maximum retention with minimum reviews.
"""

from datetime import datetime, timedelta
from enum import IntEnum
from dataclasses import dataclass
from typing import Tuple, Optional
import math
import random

# ============================================================
# CONSTANTS & ENUMS
# ============================================================

class State(IntEnum):
    """Card states in the FSRS algorithm"""
    NEW = 0        # Never reviewed
    LEARNING = 1   # In initial learning phase
    REVIEW = 2     # Graduated, in long-term review
    RELEARNING = 3 # Forgot during review, relearning

class Rating(IntEnum):
    """User rating for card difficulty"""
    AGAIN = 1  # Complete blackout, wrong answer
    HARD = 2   # Correct but with significant difficulty
    GOOD = 3   # Correct with some hesitation
    EASY = 4   # Perfect recall, effortless

# ============================================================
# FSRS PARAMETERS (FSRS-4.5 default weights)
# These 19 parameters control the algorithm behavior
# ============================================================

# Default parameters from FSRS-4.5 (can be optimized per user)
DEFAULT_WEIGHTS = [
    0.4072,   # w[0]: Initial stability for Again
    1.1829,   # w[1]: Initial stability for Hard
    3.1262,   # w[2]: Initial stability for Good
    15.4722,  # w[3]: Initial stability for Easy
    7.2102,   # w[4]: Difficulty weight
    0.5316,   # w[5]: Stability decay
    1.0651,   # w[6]: Recall stability factor
    0.0234,   # w[7]: Difficulty-stability interaction
    1.616,    # w[8]: Forgetting curve shape
    0.1544,   # w[9]: Hard penalty
    1.0824,   # w[10]: Easy bonus
    1.9813,   # w[11]: Review stability growth
    0.0953,   # w[12]: Relearning stability factor
    0.2975,   # w[13]: Difficulty penalty on stability
    2.2261,   # w[14]: Short-term stability factor
    0.2553,   # w[15]: Short-term stability decay
    0.0,      # w[16]: Reserved
    2.7,      # w[17]: Fuzz factor minimum days
    0.05,     # w[18]: Fuzz range percentage
]

# Algorithm constants
DECAY = -0.5
FACTOR = 19 / 81  # 0.9^(1/DECAY) - 1

# Learning steps in minutes [1min, 10min]
LEARNING_STEPS = [1, 10]

# Relearning steps in minutes [10min]
RELEARNING_STEPS = [10]

# Graduating interval (days after passing learning)
GRADUATING_INTERVAL = 1

# Easy interval (days for Easy on new card)
EASY_INTERVAL = 4

# Maximum interval cap (days)
MAXIMUM_INTERVAL = 36500  # ~100 years

# Desired retention rate (90% is Anki's default)
REQUEST_RETENTION = 0.9

# ============================================================
# FSRS CORE FUNCTIONS
# ============================================================

@dataclass
class SchedulingInfo:
    """Information about a scheduled review"""
    state: State
    stability: float      # In days
    difficulty: float     # 1-10
    scheduled_days: int   # Interval in days
    due_date: datetime
    reps: int
    lapses: int
    step: int

def init_difficulty(rating: Rating, w: list = DEFAULT_WEIGHTS) -> float:
    """
    Initialize difficulty for a new card based on first rating.
    Formula: D0(G) = w[4] - exp(w[5] * (G - 1)) + 1
    Clamped to [1, 10]
    """
    d = w[4] - math.exp(w[5] * (rating - 1)) + 1
    return max(1.0, min(10.0, d))

def init_stability(rating: Rating, w: list = DEFAULT_WEIGHTS) -> float:
    """
    Initialize stability for a new card based on first rating.
    S0(G) = w[G-1] where G is rating (1-4)
    """
    return max(0.1, w[rating - 1])

def forgetting_curve(elapsed_days: float, stability: float) -> float:
    """
    Calculate the probability of recall given elapsed time and stability.
    Formula: R(t,S) = (1 + FACTOR * t/S)^DECAY

    Returns: Retrievability (probability 0-1)
    """
    if stability <= 0:
        return 0.0
    return math.pow(1 + FACTOR * elapsed_days / stability, DECAY)

def next_interval(stability: float, request_retention: float = REQUEST_RETENTION) -> int:
    """
    Calculate the optimal interval for desired retention.
    Formula: I(S,R) = S / FACTOR * (R^(1/DECAY) - 1)

    Returns: Interval in days (clamped to [1, MAXIMUM_INTERVAL])
    """
    if stability <= 0:
        return 1

    interval = stability / FACTOR * (math.pow(request_retention, 1 / DECAY) - 1)
    return max(1, min(MAXIMUM_INTERVAL, round(interval)))

def next_difficulty(d: float, rating: Rating, w: list = DEFAULT_WEIGHTS) -> float:
    """
    Update difficulty after a review.
    Formula: D'(D,G) = w[6] * D0(3) + (1 - w[6]) * (D - w[7] * (G - 3))

    Uses mean reversion toward initial difficulty of Good rating.
    """
    # Delta from Good rating
    delta = -(w[7] * (rating - 3))

    # Mean reversion factor
    mean_reversion = w[6] * init_difficulty(Rating.GOOD, w) + (1 - w[6]) * (d + delta)

    return max(1.0, min(10.0, mean_reversion))

def next_recall_stability(
    d: float,
    s: float,
    r: float,
    rating: Rating,
    w: list = DEFAULT_WEIGHTS
) -> float:
    """
    Calculate new stability after a successful recall (Hard, Good, Easy).

    Formula: S'_r(D,S,R,G) = S * (e^w[8] * (11-D) * S^(-w[9]) * (e^(w[10]*(1-R))-1) * hard_penalty * easy_bonus + 1)
    """
    hard_penalty = w[15] if rating == Rating.HARD else 1.0
    easy_bonus = w[16] if rating == Rating.EASY else 1.0

    # Core stability growth formula
    new_s = s * (
        math.exp(w[8]) *
        (11 - d) *
        math.pow(s, -w[9]) *
        (math.exp(w[10] * (1 - r)) - 1) *
        hard_penalty *
        easy_bonus + 1
    )

    return max(0.1, new_s)

def next_forget_stability(
    d: float,
    s: float,
    r: float,
    w: list = DEFAULT_WEIGHTS
) -> float:
    """
    Calculate new stability after forgetting (Again rating).

    Formula: S'_f(D,S,R) = w[11] * D^(-w[12]) * ((S+1)^w[13] - 1) * e^(w[14]*(1-R))
    """
    new_s = (
        w[11] *
        math.pow(d, -w[12]) *
        (math.pow(s + 1, w[13]) - 1) *
        math.exp(w[14] * (1 - r))
    )

    return max(0.1, min(s, new_s))  # Can't be higher than previous stability

def next_short_term_stability(s: float, rating: Rating, w: list = DEFAULT_WEIGHTS) -> float:
    """
    Calculate stability change during learning/relearning phases.

    Formula: S'_s(S,G) = S * e^(w[17] * (G - 3 + w[18]))
    """
    new_s = s * math.exp(w[14] * (rating - 3 + w[15]))
    return max(0.1, new_s)

def apply_fuzz(interval: int, min_fuzz_days: float = 2.5) -> int:
    """
    Add randomization to prevent cards from clustering.
    Only applies to intervals >= min_fuzz_days.
    """
    if interval < min_fuzz_days:
        return interval

    # Calculate fuzz range (approximately ±5% with minimum of 1 day)
    fuzz_range = max(1, round(interval * 0.05))

    # Apply random fuzz
    return interval + random.randint(-fuzz_range, fuzz_range)

# ============================================================
# MAIN SCHEDULING FUNCTION
# ============================================================

def calculate_next_review(
    # Current card state
    current_state: int,
    current_stability: int,  # Stored as days * 100
    current_difficulty: int,  # Stored as value * 100
    current_scheduled_days: int,
    current_reps: int,
    current_lapses: int,
    current_step: int,
    last_review: Optional[datetime],
    # User input
    rating: int,
    # Optional parameters
    weights: list = DEFAULT_WEIGHTS,
    request_retention: float = REQUEST_RETENTION
) -> dict:
    """
    Main FSRS scheduling function.

    Calculates the next review parameters based on current card state and user rating.

    Args:
        current_state: Card state (0=New, 1=Learning, 2=Review, 3=Relearning)
        current_stability: Stability in days * 100 (e.g., 250 = 2.5 days)
        current_difficulty: Difficulty * 100 (e.g., 500 = 5.0)
        current_scheduled_days: Current interval
        current_reps: Number of successful reviews
        current_lapses: Number of times forgot
        current_step: Current learning step
        last_review: When card was last reviewed
        rating: User rating (1=Again, 2=Hard, 3=Good, 4=Easy)
        weights: FSRS parameters
        request_retention: Target retention rate

    Returns:
        Dictionary with updated scheduling parameters
    """
    now = datetime.utcnow()

    # Convert stored values to float
    stability = current_stability / 100.0 if current_stability > 0 else 0.0
    difficulty = current_difficulty / 100.0 if current_difficulty > 0 else 0.0

    # Calculate elapsed time since last review
    elapsed_days = 0.0
    if last_review:
        elapsed_days = (now - last_review).total_seconds() / 86400.0  # Convert to days

    # Calculate current retrievability
    retrievability = forgetting_curve(elapsed_days, stability) if stability > 0 else 0.0

    # Initialize result
    new_state = current_state
    new_stability = stability
    new_difficulty = difficulty
    new_scheduled_days = 0
    new_reps = current_reps
    new_lapses = current_lapses
    new_step = current_step

    # Convert rating to enum
    r = Rating(rating)

    # ============================================================
    # STATE MACHINE LOGIC
    # ============================================================

    if current_state == State.NEW:
        # First time seeing this card
        new_difficulty = init_difficulty(r, weights)
        new_stability = init_stability(r, weights)

        if r == Rating.AGAIN:
            # Failed on first try - enter learning
            new_state = State.LEARNING
            new_step = 0
            new_scheduled_days = 0  # Will use learning steps (minutes)
            # Due in 1 minute
            due_date = now + timedelta(minutes=LEARNING_STEPS[0])
        elif r == Rating.HARD:
            # Hard but got it - enter learning
            new_state = State.LEARNING
            new_step = 0
            new_scheduled_days = 0
            due_date = now + timedelta(minutes=LEARNING_STEPS[0])
        elif r == Rating.GOOD:
            # Good - graduate to review
            new_state = State.REVIEW
            new_step = 0
            new_reps = 1
            new_scheduled_days = GRADUATING_INTERVAL
            due_date = now + timedelta(days=GRADUATING_INTERVAL)
        else:  # EASY
            # Easy - graduate with longer interval
            new_state = State.REVIEW
            new_step = 0
            new_reps = 1
            new_scheduled_days = EASY_INTERVAL
            due_date = now + timedelta(days=EASY_INTERVAL)

    elif current_state == State.LEARNING:
        # In learning phase
        if r == Rating.AGAIN:
            # Reset to beginning of learning
            new_step = 0
            new_stability = init_stability(r, weights)
            due_date = now + timedelta(minutes=LEARNING_STEPS[0])
        elif r == Rating.HARD:
            # Stay at current step
            step_minutes = LEARNING_STEPS[min(new_step, len(LEARNING_STEPS) - 1)]
            new_stability = next_short_term_stability(stability if stability > 0 else init_stability(r, weights), r, weights)
            due_date = now + timedelta(minutes=step_minutes)
        elif r == Rating.GOOD:
            # Advance to next step or graduate
            new_step += 1
            new_stability = next_short_term_stability(stability if stability > 0 else init_stability(r, weights), r, weights)

            if new_step >= len(LEARNING_STEPS):
                # Graduate to review
                new_state = State.REVIEW
                new_step = 0
                new_reps = 1
                new_scheduled_days = max(GRADUATING_INTERVAL, next_interval(new_stability, request_retention))
                due_date = now + timedelta(days=new_scheduled_days)
            else:
                # Continue learning
                step_minutes = LEARNING_STEPS[new_step]
                due_date = now + timedelta(minutes=step_minutes)
        else:  # EASY
            # Immediately graduate with bonus
            new_state = State.REVIEW
            new_step = 0
            new_reps = 1
            new_stability = next_short_term_stability(stability if stability > 0 else init_stability(r, weights), r, weights)
            new_scheduled_days = max(EASY_INTERVAL, next_interval(new_stability, request_retention))
            due_date = now + timedelta(days=new_scheduled_days)

    elif current_state == State.REVIEW:
        # In review phase
        new_difficulty = next_difficulty(difficulty, r, weights)

        if r == Rating.AGAIN:
            # Forgot - enter relearning
            new_state = State.RELEARNING
            new_step = 0
            new_lapses += 1
            new_stability = next_forget_stability(difficulty, stability, retrievability, weights)
            due_date = now + timedelta(minutes=RELEARNING_STEPS[0])
        else:
            # Successful recall
            new_reps += 1
            new_stability = next_recall_stability(difficulty, stability, retrievability, r, weights)
            new_scheduled_days = next_interval(new_stability, request_retention)

            # Apply fuzz to prevent clustering
            new_scheduled_days = apply_fuzz(new_scheduled_days)

            # Ensure Hard < Good < Easy intervals
            if r == Rating.HARD:
                new_scheduled_days = max(1, min(new_scheduled_days, current_scheduled_days + 1))
            elif r == Rating.EASY:
                good_interval = next_interval(next_recall_stability(difficulty, stability, retrievability, Rating.GOOD, weights), request_retention)
                new_scheduled_days = max(new_scheduled_days, good_interval + 1)

            due_date = now + timedelta(days=new_scheduled_days)

    elif current_state == State.RELEARNING:
        # Relearning after forgetting
        if r == Rating.AGAIN:
            # Reset relearning
            new_step = 0
            due_date = now + timedelta(minutes=RELEARNING_STEPS[0])
        elif r == Rating.HARD:
            # Stay at current step
            step_minutes = RELEARNING_STEPS[min(new_step, len(RELEARNING_STEPS) - 1)]
            due_date = now + timedelta(minutes=step_minutes)
        elif r == Rating.GOOD:
            # Advance or graduate back to review
            new_step += 1

            if new_step >= len(RELEARNING_STEPS):
                # Graduate back to review
                new_state = State.REVIEW
                new_step = 0
                new_scheduled_days = max(1, next_interval(new_stability, request_retention))
                due_date = now + timedelta(days=new_scheduled_days)
            else:
                step_minutes = RELEARNING_STEPS[new_step]
                due_date = now + timedelta(minutes=step_minutes)
        else:  # EASY
            # Immediately return to review with bonus
            new_state = State.REVIEW
            new_step = 0
            new_stability = next_recall_stability(difficulty, new_stability, 0.0, r, weights)
            new_scheduled_days = max(1, next_interval(new_stability, request_retention))
            due_date = now + timedelta(days=new_scheduled_days)

    # ============================================================
    # PREPARE RESULT
    # ============================================================

    return {
        "state": int(new_state),
        "stability": int(new_stability * 100),  # Store as days * 100
        "difficulty": int(new_difficulty * 100),  # Store as value * 100
        "scheduled_days": new_scheduled_days,
        "due_date": due_date,
        "reps": new_reps,
        "lapses": new_lapses,
        "step": new_step,
        "last_review": now,
        # Additional info for frontend
        "retrievability": round(retrievability * 100, 1),  # Percentage
    }

def get_next_intervals(
    current_state: int,
    current_stability: int,
    current_difficulty: int,
    current_scheduled_days: int,
    last_review: Optional[datetime],
    weights: list = DEFAULT_WEIGHTS,
    request_retention: float = REQUEST_RETENTION
) -> dict:
    """
    Preview the intervals for each rating option.
    Useful for displaying to the user what each button will do.

    Returns:
        Dictionary with interval preview for each rating
    """
    now = datetime.utcnow()
    stability = current_stability / 100.0 if current_stability > 0 else 0.0
    difficulty = current_difficulty / 100.0 if current_difficulty > 0 else 5.0

    elapsed_days = 0.0
    if last_review:
        elapsed_days = (now - last_review).total_seconds() / 86400.0

    retrievability = forgetting_curve(elapsed_days, stability) if stability > 0 else 0.0

    intervals = {}

    for rating in [Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY]:
        if current_state == State.NEW:
            if rating == Rating.AGAIN or rating == Rating.HARD:
                intervals[rating.name.lower()] = f"{LEARNING_STEPS[0]}m"
            elif rating == Rating.GOOD:
                intervals[rating.name.lower()] = f"{GRADUATING_INTERVAL}j"
            else:
                intervals[rating.name.lower()] = f"{EASY_INTERVAL}j"

        elif current_state == State.LEARNING:
            if rating == Rating.AGAIN:
                intervals[rating.name.lower()] = f"{LEARNING_STEPS[0]}m"
            elif rating == Rating.HARD:
                intervals[rating.name.lower()] = f"{LEARNING_STEPS[0]}m"
            elif rating == Rating.GOOD:
                if len(LEARNING_STEPS) > 1:
                    intervals[rating.name.lower()] = f"{LEARNING_STEPS[1]}m"
                else:
                    intervals[rating.name.lower()] = f"{GRADUATING_INTERVAL}j"
            else:
                intervals[rating.name.lower()] = f"{EASY_INTERVAL}j"

        elif current_state == State.REVIEW:
            if rating == Rating.AGAIN:
                intervals[rating.name.lower()] = f"{RELEARNING_STEPS[0]}m"
            else:
                new_s = next_recall_stability(difficulty, stability, retrievability, rating, weights)
                interval = next_interval(new_s, request_retention)

                if rating == Rating.HARD:
                    interval = max(1, min(interval, current_scheduled_days + 1))
                elif rating == Rating.EASY:
                    good_interval = next_interval(
                        next_recall_stability(difficulty, stability, retrievability, Rating.GOOD, weights),
                        request_retention
                    )
                    interval = max(interval, good_interval + 1)

                if interval >= 365:
                    intervals[rating.name.lower()] = f"{round(interval / 365, 1)}a"
                elif interval >= 30:
                    intervals[rating.name.lower()] = f"{round(interval / 30, 1)}mo"
                else:
                    intervals[rating.name.lower()] = f"{interval}j"

        elif current_state == State.RELEARNING:
            if rating == Rating.AGAIN or rating == Rating.HARD:
                intervals[rating.name.lower()] = f"{RELEARNING_STEPS[0]}m"
            elif rating == Rating.GOOD:
                if len(RELEARNING_STEPS) > 1:
                    intervals[rating.name.lower()] = f"{RELEARNING_STEPS[0]}m"
                else:
                    interval = max(1, next_interval(stability, request_retention))
                    intervals[rating.name.lower()] = f"{interval}j"
            else:
                interval = max(1, next_interval(stability, request_retention))
                intervals[rating.name.lower()] = f"{interval}j"

    return intervals

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def state_to_string(state: int) -> str:
    """Convert state integer to human-readable string"""
    states = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
    return states.get(state, "unknown")

def string_to_state(state_str: str) -> int:
    """Convert state string to integer"""
    states = {"new": 0, "learning": 1, "review": 2, "relearning": 3}
    return states.get(state_str.lower(), 0)

def get_card_retrievability(
    stability: int,
    last_review: Optional[datetime]
) -> float:
    """
    Calculate current retrievability of a card.

    Returns: Probability of recall (0-1)
    """
    if not last_review or stability <= 0:
        return 1.0

    elapsed_days = (datetime.utcnow() - last_review).total_seconds() / 86400.0
    s = stability / 100.0

    return forgetting_curve(elapsed_days, s)

def format_interval(days: int) -> str:
    """Format interval in human-readable format"""
    if days == 0:
        return "maintenant"
    elif days < 1:
        minutes = int(days * 24 * 60)
        return f"{minutes}m"
    elif days < 30:
        return f"{days}j"
    elif days < 365:
        months = round(days / 30, 1)
        return f"{months}mo"
    else:
        years = round(days / 365, 1)
        return f"{years}a"
