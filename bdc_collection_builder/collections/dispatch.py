from bdc_catalog.models import db

from .models import ActivitySRC, RadcorActivity
from .utils import get_or_create_model


def create_activity_definition(collection_id, activity_type, scene, **kwargs):
    return dict(
        collection_id=collection_id,
        activity_type=activity_type,
        tags=kwargs.get('tags', []),
        sceneid=scene.scene_id,
        scene_type='SCENE',
        args=dict(
            cloud=scene.cloud_cover,
            **kwargs
        )
    )


def create_activity(activity, parent=None):
    """Persist an activity on database."""
    where = dict(
        sceneid=activity['sceneid'],
        activity_type=activity['activity_type'],
        collection_id=activity['collection_id']
    )

    model, created = get_or_create_model(RadcorActivity, defaults=activity, **where)

    if created:
        db.session.add(model)

    if parent:
        relation_defaults = dict(
            activity=model,
            parent=parent
        )

        _relation, _created = get_or_create_model(
            ActivitySRC,
            defaults=relation_defaults,
            **relation_defaults
        )

    return model, created
