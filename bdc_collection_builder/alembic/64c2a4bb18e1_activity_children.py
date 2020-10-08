"""activity_children

Revision ID: 64c2a4bb18e1
Revises: 
Create Date: 2020-10-03 23:20:32.253182

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64c2a4bb18e1'
down_revision = '06fab6583881'
branch_labels = ()
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('activity_src',
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('activity_src_id', sa.Integer(), nullable=False),
    sa.Column('created', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['collection_builder.activities.id'], name=op.f('activity_src_activity_id_activities_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['activity_src_id'], ['collection_builder.activities.id'], name=op.f('activity_src_activity_src_id_activities_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('activity_id', 'activity_src_id', name=op.f('activity_src_pkey')),
    schema='collection_builder'
    )
    op.create_unique_constraint(op.f('activities_collection_id_key'), 'activities',
                                ['collection_id', 'activity_type', 'sceneid'], schema='collection_builder')
    op.drop_constraint('activity_history_task_id_celery_taskmeta_fkey', 'activity_history', schema='collection_builder',
                       type_='foreignkey')
    op.create_foreign_key(op.f('activity_history_task_id_celery_taskmeta_fkey'), 'activity_history', 'celery_taskmeta',
                          ['task_id'], ['id'], source_schema='collection_builder', onupdate='CASCADE', referent_schema='collection_builder',
                          ondelete='CASCADE')
    op.drop_constraint('activity_history_activity_id_activities_fkey', 'activity_history', schema='collection_builder',
                       type_='foreignkey')
    op.create_foreign_key(op.f('activity_history_activity_id_activities_fkey'), 'activity_history', 'activities',
                          ['activity_id'], ['id'], source_schema='collection_builder', onupdate='CASCADE',
                          referent_schema='collection_builder',
                          ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(op.f('activity_history_activity_id_activities_fkey'), 'activity_history', schema='collection_builder', type_='foreignkey')
    op.create_foreign_key('activity_history_activity_id_activities_fkey', 'activity_history', 'activities', ['activity_id'], ['id'], source_schema='collection_builder', referent_schema='collection_builder')
    op.drop_constraint(op.f('activity_history_task_id_celery_taskmeta_fkey'), 'activity_history', schema='collection_builder', type_='foreignkey')
    op.create_foreign_key('activity_history_task_id_celery_taskmeta_fkey', 'activity_history', 'collection_builder.celery_taskmeta', ['task_id'], ['id'], source_schema='collection_builder', referent_schema='collection_builder')
    op.drop_constraint(op.f('activities_collection_id_key'), 'activities', schema='collection_builder', type_='unique')
    op.drop_table('activity_src', schema='collection_builder')
    # ### end Alembic commands ###