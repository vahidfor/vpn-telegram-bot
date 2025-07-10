from telegram.ext import ConversationHandler

REQUEST_INFO, = range(1)
PRICE_CONFIG, ADD_CREDIT, DEDUCT_CREDIT = range(3,6)
SEND_SERVICE, REJECT_SERVICE = range(6,8)
