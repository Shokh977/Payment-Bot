from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    waiting_for_code       = State()
    code_verified          = State()
    waiting_for_screenshot = State()
    confirming_cancel      = State()


class AdminApprovalStates(StatesGroup):
    selecting_payment_method = State()
    confirming_amount        = State()
    entering_custom_amount   = State()
    final_confirmation       = State()
    selecting_reject_reason  = State()
    entering_custom_reason   = State()
