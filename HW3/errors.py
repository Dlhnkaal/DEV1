class AdvertisementNotFoundError(Exception):
    #Объявление не найдено в базе данных
    pass

class UserNotFoundError(Exception):
    #Пользователь не найден в базе данных
    pass

class ModelNotReadyError(Exception):
    #ML модель не готова к использованию
    pass