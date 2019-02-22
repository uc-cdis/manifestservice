from cdiserrors import *
from authutils.errors import JWTError

class CustomException(APIError):
    def __init__(self, message):
        self.message = str(message)
        self.code = 500



class UserError(APIError):
    '''
    User error.
    '''
    def __init__(self, message):
        self.message = str(message)
        self.code = 400