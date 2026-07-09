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

    def set_module(self, name, score):
        if name in self.modules:
            self.modules[name] = max(0, min(score, 25))

    def total(self):
        return sum(self.modules.values())

    def momofit(self):
        return max(0, min(self.total(), 100))

    def summary(self):
        return self.modules
