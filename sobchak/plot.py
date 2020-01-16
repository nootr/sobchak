from io import BytesIO
from matplotlib import pyplot, patches
import base64

class Plot(object):
    """Plot

    Generates a graph and converts it to a base64-decoded PNG file.
    """

    def __init__(self, width, height, title, xlabel, ylabel):
        self.width = width
        self.height = height
        self._png_file = BytesIO()

        pyplot.xlim(1.1 * width)
        pyplot.ylim(1.1 * height)
        pyplot.gca().invert_xaxis()
        pyplot.gca().invert_yaxis()
        pyplot.title(title)
        pyplot.xlabel(xlabel)
        pyplot.ylabel(ylabel)

    def __del__(self):
        """__del__

        Make sure the plot is cleared when this object is destructed.
        """
        pyplot.clf()

    def add_graph(self, x, y, label):
        """add_graph

        Turn two lists representing x and y values into a plot and add it to
        the graph.
        """
        pyplot.plot(x[:len(y)], y[:len(x)], label=label)

    def add_box(self, width, height, label=None, facecolor='none', color='b'):
        """add_box

        Add a box with a given width and height of a given color (blue by
        default) to the graph.
        """
        rect = patches.Rectangle(
            (0, 0),
            width,
            height,
            linewidth=1,
            edgecolor=color,
            label=label,
            facecolor=facecolor)
        pyplot.gca().add_patch(rect)

    @property
    def png(self):
        """png

        Saves the current plot to the in-memory PNG file and returns the file.
        """
        pyplot.legend(loc='lower right')
        pyplot.savefig(self._png_file, format='png')
        return self._png_file

    @property
    def base64(self):
        """base64

        Returns a base64-decoded string of the graph.
        """
        image = self.png.getvalue()
        return base64.encodestring(image).decode('utf-8')
