"""Render one cell of the locally stored nursery illustration atlas."""
from django.conf import settings
from reportlab.platypus import Flowable


ILLUSTRATIONS = ('social', 'environment', 'hygiene', 'numbers', 'language', 'oral', 'writing', 'physical')


class NurseryPicture(Flowable):
    def __init__(self, illustration, size=32):
        super().__init__()
        self.illustration = illustration
        self.width = self.height = size

    def draw(self):
        if self.illustration not in ILLUSTRATIONS:
            return
        index = ILLUSTRATIONS.index(self.illustration)
        column, row = index % 2, index // 2
        c, size = self.canv, self.width
        c.saveState()
        clip = c.beginPath()
        clip.rect(0, 0, size, size)
        c.clipPath(clip, stroke=0)
        top, bottom = [(0, 444), (444, 858), (858, 1320), (1320, 1774)][row]
        scale = size / (bottom - top)
        c.drawImage(str(settings.BASE_DIR / 'static/img/nursery-learning-atlas.png'),
                    -column * size, -(1774-bottom)*scale, width=2*size, height=1774*scale)
        c.restoreState()
