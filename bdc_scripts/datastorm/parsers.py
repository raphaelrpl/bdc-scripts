from marshmallow import Schema, fields


class DataCubeBandParser(Schema):
    names = fields.List(fields.String, required=True, allow_none=False)
    min = fields.Integer(required=True, allow_none=False)
    max = fields.Integer(required=True, allow_none=False)
    fill = fields.Integer(required=True, allow_none=False)
    scale = fields.Integer(required=True, allow_none=False)
    data_type = fields.String(required=True, allow_none=False)


class DataCubeParser(Schema):
    datacube = fields.String(required=True, allow_none=False)
    grs = fields.String(required=True, allow_none=False)
    resolution = fields.Integer(required=True, allow_none=False)
    temporal_schema = fields.String(required=True, allow_none=False)
    bands_quicklook = fields.List(fields.String, required=True, allow_none=False)
    composite_function_list = fields.List(fields.String, required=True, allow_none=False)
    bands = fields.Nested(DataCubeBandParser, required=True)
    description = fields.String(required=True, allow_none=False)


class DataCubeProcessParser(Schema):
    datacube = fields.String(required=True, allow_none=False)
    collections = fields.List(fields.String, required=True, allow_none=False)
    tiles = fields.List(fields.String, required=True, allow_none=False)
    start_date = fields.Date()
    end_date = fields.Date()