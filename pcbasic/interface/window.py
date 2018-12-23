"""
PC-BASIC - window.py
Graphical interface common utilities

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

try:
    import numpy
except ImportError:
    numpy = None

from ..compat import set_dpi_aware


# Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
set_dpi_aware()

# percentage of the screen to leave unused for window decorations etc.
DISPLAY_SLACK = 15
_SLACK_RATIO = 1. - DISPLAY_SLACK / 100.


def apply_composite_artifacts(src_array, pixels=4):
    """Process the canvas to apply composite colour artifacts."""
    width, _ = src_array.shape
    s = [None] * pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels] & (4//pixels)
    for p in range(1, pixels):
        s[0] = s[0]*2 + s[p]
    return numpy.repeat(s[0], pixels, axis=0)


def _most_constraining(constraining, target_aspect):
    """Find most constraining dimension to scale."""
    # we're assuming native pixels are square
    # so physical screen's aspect ratio is simply ratio of pixel numbers
    if constraining[0] / float(constraining[1]) >= target_aspect[0] / float(target_aspect[1]):
        # constraining screen has wider aspect than target screen
        # so Y is the constraining dimension
        # +------------+
        # |     +----+ |
        # |     |    | |
        # |     +----+ |
        # +------------+
        return 1
    else:
        # constraining screen has taller aspect than target screen
        # so X is the constraining dimension
        # +-----------+
        # | +-------+ |
        # | |       | |
        # | +-------+ |
        # |           |
        # +-----------+
        return 0


class WindowSizer(object):
    """Physical/logical window size operations."""

    def __init__(self, screen_width, screen_height,
            scaling=None, dimensions=None, aspect_ratio=(4, 3), border_width=0,
            **kwargs
        ):
        """Initialise size parameters."""
        # use native pixel sizes
        # i.e. logical pixel boundaries coincide with physical pixel boundaries
        self._force_native_pixel = scaling == 'native'
        # override physical pixel size of window
        self._force_window_size = dimensions
        # canvas aspect ratio
        self._aspect = aspect_ratio
        # border width as a percentage of canvas width
        self._border_pct = border_width
        # the following attributes must be set separately
        # physical pixel size of screen
        self._screen_size = screen_width, screen_height
        # logical pixel size of canvas
        self._canvas_logical = ()
        # physical pixel size of window (canvas+border)
        self._window_size = ()
        # physical pixel size of display (canvas+border+letterbox)
        self._display_size = ()

    def normalise_pos(self, x, y):
        """Convert physical to logical coordinates within screen bounds."""
        if not self._canvas_logical or not self._window_size:
            # window not initialised
            return 0, 0
        border_shift = self.border_shift
        letterbox_shift = self.letterbox_shift
        scale = self.scale
        xpos = min(self._canvas_logical[0] - 1, max(
            0, int((x-letterbox_shift[0]) // scale[0] - border_shift[0])
        ))
        ypos = min(self._canvas_logical[1] - 1, max(
            0, int((y-letterbox_shift[1]) // scale[1] - border_shift[1])
        ))
        return xpos, ypos

    def set_canvas_size(
            self, canvas_x, canvas_y,
            resize_window=True, fullscreen=False
        ):
        """Change the logical canvas size and determine window/display sizes."""
        self._canvas_logical = canvas_x, canvas_y
        if not resize_window and not self._force_native_pixel:
            return False
        old_display_size = self._display_size
        old_window_size = self._display_size
        # comply with requested size
        if self._force_window_size:
            self._window_size = self._force_window_size
        else:
            slack_ratio = _SLACK_RATIO if not fullscreen else 1.
            if not self._force_native_pixel:
                self._window_size = self._find_nonnative_window_size(slack_ratio)
            else:
                self._window_size = self._find_native_window_size(slack_ratio)
        if fullscreen:
            self._display_size = self._screen_size
        else:
            self._display_size = self._window_size
        return self._display_size != old_display_size or self._window_size != old_window_size

    def set_display_size(self, new_size_x, new_size_y):
        """Change the physical display size."""
        self._window_size = new_size_x, new_size_y
        self._display_size = self._window_size

    def _find_nonnative_window_size(self, slack_ratio):
        """Determine the optimal size for a non-natively scaled window."""
        # border is given as a percentage of canvas size
        border_ratio = 1. + self._border_pct / 100.
        # shrink the window in the most constraining dimension
        mcd = _most_constraining(self._screen_size, self._aspect)
        lcd = 1 - mcd
        # scale MCD to fit screen height, leaving slack
        canvas = [0, 0]
        canvas[mcd] = slack_ratio * self._screen_size[mcd] / border_ratio
        # scale LCD to match aspect ratio
        canvas[lcd] = (canvas[mcd] * self._aspect[lcd]) / float(self._aspect[mcd])
        # add back border and ensure pixel sizes are integers
        return int(canvas[0] * border_ratio), int(canvas[1] * border_ratio)

    def _find_native_window_size(self, slack_ratio):
        """Determine the optimal size for a natively scaled window."""
        # logical-pixel window size
        logical = self.window_size_logical
        # shrink the window in the most constraining dimension
        mcd = _most_constraining(self._screen_size, self._aspect)
        lcd = 1 - mcd
        # find the integer multiplier for the most constraining dimension by rounding down
        mult = [1, 1]
        mult[mcd] = max(1, int(slack_ratio * self._screen_size[mcd] / float(logical[mcd])))
        # find the integer multiplier for the other dimension
        # such that we get closest to the target aspect ratio
        target_aspect_ratio = self._aspect[lcd] / float(self._aspect[mcd])
        target_lcd = mult[mcd] * logical[mcd] * target_aspect_ratio / logical[lcd]
        mult[lcd] = max(1, int(target_lcd))
        if mult[lcd] + 1 - target_lcd < target_lcd - mult[lcd]:
            mult[lcd] += 1
        # physical-pixel window size
        return mult[0]*logical[0], mult[1]*logical[1]

    @property
    def scale(self):
        """Get scale factors from logical to window size."""
        border_x, border_y = self.border_shift
        return (
            self._window_size[0] / (self._canvas_logical[0] + 2.0*border_x),
            self._window_size[1] / (self._canvas_logical[1] + 2.0*border_y)
        )

    @property
    def border_shift(self):
        """Top left logical coordinates of canvas relative to window."""
        return (
            int(self._canvas_logical[0] * self._border_pct / 200.),
            int(self._canvas_logical[1] * self._border_pct / 200.)
        )

    @property
    def letterbox_shift(self):
        """Top left physical coordinates of letterbox relative to screen."""
        return (
            int(max(0., self._display_size[0] - self._window_size[0]) // 2),
            int(max(0., self._display_size[1] - self._window_size[1]) // 2)
        )

    @property
    def window_size_logical(self):
        """Window (canvas+border) size in logical pixels."""
        # express border as interger number of logical pixels
        border = self.border_shift
        return self._canvas_logical[0] + 2 * border[0], self._canvas_logical[1] + 2 * border[1]

    @property
    def window_size(self):
        """Window (canvas+border) size in physical pixels."""
        return self._window_size

    @property
    def display_size(self):
        """Display (canvas+border+letterbox) size in physical pixels."""
        return self._display_size

    @property
    def screen_size(self):
        """Width and height of physical screen in pixels."""
        return self._screen_size
