from cdiserrors import *
from authutils.errors import JWTError

class UserError(APIError):
    '''
    User error.
    '''
    def __init__(self, message):
        self.message = str(message)
        self.code = 400