# define locations to store the rendered data

from boto import connect_s3
from boto.s3.bucket import Bucket
import md5
import os


def calc_hash(s):
    m = md5.new()
    m.update(s)
    md5_hash = m.hexdigest()
    return md5_hash[:5]


def s3_tile_key(date, path, layer, coord, extension):
    path_to_hash = '/%(path)s/%(layer)s/%(z)d/%(x)d/%(y)d.%(ext)s' % dict(
        path=path,
        layer=layer,
        z=coord.zoom,
        x=coord.column,
        y=coord.row,
        ext=extension,
    )
    md5_hash = calc_hash(path_to_hash)
    s3_path = '/%(date)s/%(md5)s%(path_to_hash)s' % dict(
        date=date,
        md5=md5_hash,
        path_to_hash=path_to_hash,
    )
    return s3_path


class S3(object):

    def __init__(
            self, bucket, layer_name, date_prefix, path, reduced_redundancy):
        self.bucket = bucket
        self.layer = layer_name
        self.date_prefix = date_prefix
        self.path = path
        self.reduced_redundancy = reduced_redundancy

    def write_tile(self, tile_data, coord, format):
        key_name = s3_tile_key(
            self.date_prefix, self.path, self.layer, coord, format.extension)
        key = self.bucket.new_key(key_name)
        key.set_contents_from_string(
            tile_data,
            headers={'Content-Type': format.mimetype},
            policy='public-read',
            reduced_redundancy=self.reduced_redundancy,
        )

    def read_tile(self, coord, format):
        key_name = s3_tile_key(
            self.date_prefix, self.path, self.layer, coord, format.extension)
        key = self.bucket.get_key(key_name)
        if key is None:
            return None
        tile_data = key.get_contents_as_string()
        return tile_data


def make_dir_path(base_path, coord):
    path = os.path.join(base_path,
                        str(int(coord.zoom)), str(int(coord.column)))
    return path


def make_file_path(base_path, coord, extension):
    basefile_path = os.path.join(
        base_path,
        str(int(coord.zoom)), str(int(coord.column)), str(int(coord.row)))
    ext_str = '.%s' % extension
    full_path = basefile_path + ext_str
    return full_path


class TileDirectory(object):
    '''
    Writes tiles to individual files in a local directory.
    '''

    def __init__(self, base_path):
        if os.path.exists(base_path):
            if not os.path.isdir(base_path):
                raise IOError(
                    '`{}` exists and is not a directory!'.format(base_path))
        else:
            os.makedirs(base_path)

        self.base_path = base_path

    def write_tile(self, tile_data, coord, format):
        dir_path = make_dir_path(self.base_path, coord)
        try:
            os.makedirs(dir_path)
        except OSError:
            pass
        file_path = make_file_path(self.base_path, coord, format.extension)
        with open(file_path, 'w') as tile_fp:
            tile_fp.write(tile_data)

    def read_tile(self, coord, format):
        file_path = make_file_path(self.base_path, coord, format.extension)
        try:
            with open(file_path, 'r') as tile_fp:
                tile_data = tile_fp.read()
            return tile_data
        except IOError:
            return None


def make_tile_file_store(base_path=None):
    if base_path is None:
        base_path = 'tiles'
    return TileDirectory(base_path)


class Memory(object):

    def __init__(self):
        self.data = None

    def write_tile(self, tile_data, coord, format):
        self.data = tile_data, coord, format

    def read_tile(self, coord, format):
        if self.data is None:
            return None
        tile_data, coord, format = self.data
        return tile_data


def make_s3_store(bucket_name,
                  aws_access_key_id=None, aws_secret_access_key=None,
                  layer_name='all', path='osm', reduced_redundancy=False,
                  date_prefix=''):
    conn = connect_s3(aws_access_key_id, aws_secret_access_key)
    bucket = Bucket(conn, bucket_name)
    s3_store = S3(bucket, layer_name, date_prefix, path, reduced_redundancy)
    return s3_store
