import random
from string import ascii_lowercase, digits

def get_four_digit_code() -> str:
    return ''.join(random.choices(ascii_lowercase + digits, k=4))