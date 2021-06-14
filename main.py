import datetime
import glob
import io
import pickle
import tkinter
from tkinter import simpledialog

import exifread
import pyheif
from PIL import ImageOps
from PIL import ImageTk, Image, ImageDraw
from PIL.ExifTags import TAGS, GPSTAGS

ipath = "/Users/kieranyoung/Downloads/"
path = ipath + "Isle Royale Photos/"
file_index = 0


# https://stackoverflow.com/questions/26392336/importing-images-from-a-directory-python-to-list-or-dictionary
def get_image_names():
    return [item for i in [glob.glob(path + '*.%s' % ext) for ext in ["jpg", "HEIC"]]
            for item in i]


def fit_me(image_dim, window_dim):
    image_w, image_h = image_dim
    window_w, window_h = window_dim
    ratio = image_w / image_h

    if image_w > window_w:
        image_w = window_w
        image_h = int(ratio * image_w)
    if image_h > window_h:
        image_h = window_h
        image_w = int(ratio * image_h)

    return image_w, image_h


def get_metadata(exifdata, verbose=False):
    metadata = {}
    # iterating over all EXIF data fields
    for tag_id in exifdata:
        # get the tag name, instead of human unreadable tag id
        tag = TAGS.get(tag_id, tag_id)
        data = exifdata.get(tag_id)
        # decode bytes
        if isinstance(data, bytes):
            data = data.decode()
        metadata[tag] = data

    if 'GPSInfo' in exifdata:
        for key in exifdata['GPSInfo'].keys():
            name = GPSTAGS.get(key, key)
            metadata[name] = exifdata['GPSInfo'][key]

    if verbose:
        for (key, data) in zip(metadata.keys(), metadata.values()):
            print(f"{key:25}: {data}")

    return metadata


def create_map(coords):
    def scale_to_img(lat_lon, h_w):
        map_coords = (48.256, -89.345, 47.791, -88.302)

        """
        Conversion from latitude and longitude to the image pixels.
        It is used for drawing the GPS records on the map image.
        :param lat_lon: GPS record to draw (lat1, lon1).
        :param h_w: Size of the map image (w, h).
        :return: Tuple containing x and y coordinates to draw on map image.
        """
        # https://gamedev.stackexchange.com/questions/33441/how-to-convert-a-number-from-one-min-max-set-to-another-min-max-set/33445
        old = (map_coords[2], map_coords[0])
        new = (0, h_w[1])
        y = ((lat_lon[0] - old[0]) * (new[1] - new[0]) / (old[1] - old[0])) + new[0]
        old = (map_coords[1], map_coords[3])
        new = (0, h_w[0])
        x = ((lat_lon[1] - old[0]) * (new[1] - new[0]) / (old[1] - old[0])) + new[0]
        # y must be reversed because the orientation of the image in the matplotlib.
        # image - (0, 0) in upper left corner; coordinate system - (0, 0) in lower left corner
        return int(x), h_w[1] - int(y)

    map_image = Image.open(ipath + 'map.jpeg')
    x1, y1 = scale_to_img(coords, (map_image.size[0], map_image.size[1]))
    draw = ImageDraw.Draw(map_image)
    scale = 12
    draw.ellipse((x1 - scale, y1 - scale, x1 + scale, y1 + scale), fill='blue', outline='blue')

    return map_image


def convert_datetime(date):
    dto = datetime.datetime.strptime(date, '%Y:%m:%d %H:%M:%S')
    return dto.strftime('%B %d, %Y  %I:%M %p')


# https://gist.github.com/omiq/da0e69234839ef8e2c0ba528953678f6
def create_viewer(files):
    global file_index
    window = tkinter.Tk()
    picture = None

    # process the interaction
    def event_action(event):
        # print(repr(event))
        event.widget.quit()

    # keys
    def right_key(event):
        global file_index
        file_index = min(file_index + 1, len(files)-1)
        event_action(event)

    def left_key(event):
        global file_index
        file_index = max(0, file_index - 1)
        event_action(event)

    def space_key(event):
        global file_index
        input = simpledialog.askstring(title="Change Image", prompt="Enter image id:")
        file_index = min(len(files)-1, max(0, int(input)))
        event_action(event)
        window.after(1, lambda: window.focus_force())

    def o_key(event):
        picture.show()

    # set up the gui
    window.bind("<Left>", left_key)
    window.bind("<Right>", right_key)
    window.bind("<space>", space_key)
    window.bind("<o>", o_key)
    # for each file, display the picture
    while True:
        _, file, date, bucko = files[file_index]

        print(file, date, bucko)
        window.title(file)

        width = window.winfo_screenwidth()
        height = window.winfo_screenheight()
        window.geometry("%dx%d" % (width, height))
        # window.geometry("{}x{}+100+100".format(picture_width, picture_height))

        # picture = Image.open(file)
        picture, _ = open_image(file)

        picture = ImageOps.exif_transpose(picture)
        picture_width = picture.size[0]
        picture_height = picture.size[1]

        picture = picture.resize(fit_me((picture_width, picture_height), (width, height)))
        tk_picture = ImageTk.PhotoImage(picture)

        image_widget = tkinter.Label(window, image=tk_picture)
        image_widget.place(x=0, y=0, width=width, height=height)

        label = tkinter.Label(window, text=f"{file_index}/{len(files)-1}   {bucko}   {convert_datetime(date)}", font='Times 40 bold')
        label.place(relx=0.5, rely=0.0, anchor='n')

        # wait for events
        window.mainloop()


def read_heic(path: str):
    with open(path, 'rb') as file:
        i = pyheif.read(file)
        for metadata in i.metadata or []:
            if metadata['type'] == 'Exif':
                fstream = io.BytesIO(metadata['data'][6:])
        # do whatever
        # Convert to other file format like jpeg
        # s = io.BytesIO()
        pi = Image.frombytes(
            mode=i.mode, size=i.size, data=i.data)
    #     image = pyheif.read(file)
    #     for metadata in image.metadata or []:
    #         if metadata['type'] == 'Exif':
    #             fstream = io.BytesIO(metadata['data'][6:])
    #
    # # now just convert to jpeg
    # pi = PIL.Image.open(fstream)
    return pi, fstream


def open_image(file):
    if file[-4:] == "HEIC":
        picture, fstream = read_heic(file)
    else:
        picture = Image.open(file)
        fstream = None
    return picture, fstream


def generate_order(files):
    files_tuples = []
    for index, file in enumerate(files):
        print(file)
        picture, fstream = open_image(file)
        metadata = get_metadata(picture.getexif() if fstream is None else exifread.process_file(fstream), verbose=False)

        try:
            if metadata['Make'] == "samsung":
                bucko = "Alex"
            elif metadata['Make'] == 'OnePlus':
                bucko = "Kieran"
        except KeyError:
            bucko = "Kevin"

        try:
            datetime = metadata['DateTime']
        except KeyError:
            datetime = str(metadata['Image DateTime'])
        tuple = (index, file, datetime, bucko)
        print(tuple)
        files_tuples.append(tuple)
    with open(ipath + "data.pkl", 'wb') as f:
        pickle.dump(files_tuples, f)


def get_order():
    with open(ipath + "data.pkl", 'rb') as f:
        return pickle.load(f)


def order_by_datetime(order):
    return sorted(order, key=lambda x: datetime.datetime.strptime(x[2], '%Y:%m:%d %H:%M:%S'))


if __name__ == '__main__':
    # names = get_image_names()
    # generate_order(names)

    order = order_by_datetime(get_order())
    create_viewer(order)

