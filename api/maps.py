import os
import urllib.parse
from faf.api.map_schema import MapSchema
from flask import request
from werkzeug.utils import secure_filename
from api import app, InvalidUsage
from api.query_commons import fetch_data

ALLOWED_EXTENSIONS = {'zip'}
MAX_PAGE_SIZE = 1000

SELECT_EXPRESSIONS = {
    'id': 'map.mapuid',
    'name': 'map.name',
    'description': 'map.description',
    'max_players': 'COALESCE(map.max_players, 0)',
    'map_type': 'map.map_type',
    'battle_type': 'map.battle_type',
    'map_sizeX': 'COALESCE(map.map_sizeX, 0)',
    'map_sizeY': 'COALESCE(map.map_sizeY, 0)',
    'version': 'map.version',
    # download_url will be URL encoded and made absolute in enrich_mod
    'download_url': "map.filename",
    # thumbnail_url_small will be URL encoded and made absolute in enrich_mod
    'thumbnail_url_small': 'map.filename',
    # thumbnail_url_large will be URL encoded and made absolute in enrich_mod
    'thumbnail_url_large': 'map.filename',
    'technical_name': "SUBSTRING(map.filename, LOCATE('/', map.filename)+1, LOCATE('.zip', map.filename)-6)",
    'downloads': 'COALESCE(features.downloads, 0)',
    'num_draws': 'COALESCE(features.num_draws, 0)',
    'rating': 'features.rating',
    'times_played': 'COALESCE(features.times_played, 0)'
}

TABLE = 'table_map map LEFT JOIN table_map_features features ON features.map_id = map.id'


@app.route('/maps/upload', methods=['POST'])
def maps_upload():
    file = request.files.get('file')
    if not file:
        raise InvalidUsage("No file has been provided")

    if not file_allowed(file.filename):
        raise InvalidUsage("Invalid file extension")

    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['MAP_UPLOAD_PATH'], filename))
    return "ok"


@app.route('/maps')
def maps():
    where = ''
    args = None
    many = True

    filename_filter = request.values.get('filter[filename]')
    if filename_filter:
        where = ' filename = %s'
        args = 'maps/' + filename_filter + '.zip'
        many = False

    results = fetch_data(MapSchema(), TABLE, SELECT_EXPRESSIONS, MAX_PAGE_SIZE, request, where=where, args=args,
                         many=many, enricher=enricher)
    return results


def enricher(map):
    if 'thumbnail_url_small' in map:
        if not map['thumbnail_url_small']:
            del map['thumbnail_url_small']
        else:
            map['thumbnail_url_small'] = '{}/faf/vault/map_previews/small/{}'.format(app.config['CONTENT_URL'],
                                                                                     map['thumbnail_url_small'])
    if 'thumbnail_url_large' in map:
        if not map['thumbnail_url_large']:
            del map['thumbnail_url_large']
        else:
            map['thumbnail_url_large'] = '{}/faf/vault/map_previews/large/{}'.format(app.config['CONTENT_URL'],
                                                                                     map['thumbnail_url_large'])

    if 'download_url' in map:
        map['download_url'] = '{}/faf/vault/{}'.format(app.config['CONTENT_URL'],
                                                       urllib.parse.quote(map['download_url']))


def file_allowed(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS
