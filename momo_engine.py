class MomoEngine:
    def __init__(self):
        self.modules = {
            "trend": 0,
            "location": 0,
            "momentum": 0,
            "volume": 0,
            "opportunity": 0,
            "risk": 0,
            "market": 0,
            "sector": 0,
        }

    def total(self):
        return sum(self.modules.values())

    def momofit(self):
        return self.total()
