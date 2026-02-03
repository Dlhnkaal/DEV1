from dataclasses import dataclass
from models.advertisement import AdvModel

@dataclass(frozen=True)
class AdvertisementService:
    def predict(self, adv: AdvModel) -> bool: 
        if adv.is_verified_seller:
            return True
        if adv.images_qty > 0:
            return True
        return False
