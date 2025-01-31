class Progress:
    def __init__(self, total: int):
        self.processed = 0
        self.total = total

    def increment(self):
        self.processed += 1

    def reset(self):
        self.processed = 0
