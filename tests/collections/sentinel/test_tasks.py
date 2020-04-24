from unittest.mock import PropertyMock, patch, call
import pytest
from celery.exceptions import Retry
from requests.exceptions import HTTPError

# Initialize Celery worker
import bdc_collection_builder.celery.worker
from bdc_collection_builder.collections.sentinel.tasks import download_sentinel


class TestSentinelTasks:
    @staticmethod
    def create_activity():
        return dict(
            activity_type='downloadS2',
            collection_id='FakeCollection',
            sceneid='S2A_MSIL1C_20000101T000000_N0000_R000_T00AAA_20000101T000000',
            args=dict(
                file='/tmp/',
                link='http://fake-link'
            )
        )

    @pytest.mark.parametrize('side_effect', [[False, False]])
    @pytest.mark.parametrize('created', [False])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_download_copernicus(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_get_or_create, mock_open):
        input_args = self.create_activity()

        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 200

        # Attaching input sceneid to the mock as property
        type(mock_activity_history.activity).sceneid = input_args['sceneid']

        # Mocking find RadcorActivityHistory
        query_property.return_value.filter.return_value.first.return_value = mock_activity_history

        res = download_sentinel(input_args)

        # Download must be called.
        mock_download_request.assert_called()

        assert type(res) == dict
        assert res['activity_type'] == 'correctionS2'
        assert res['args']['file'] == input_args['args']['file']

    # Mocking return order of Zip. First of all, a check is made
    # The first test must be a valid zip (corrupt=False).
    # The second test must return False in order to mock as valid zip
    @pytest.mark.parametrize('side_effect', [[False, False]])
    @pytest.mark.parametrize('created', [False])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_skip_download_zip_exists(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_os_path_exists, mock_get_or_create):
        input_args = self.create_activity()

        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 200

        # Attaching input sceneid to the mock as property
        type(mock_activity_history.activity).sceneid = input_args['sceneid']

        # Mocking find RadcorActivityHistory
        query_property.return_value.filter.return_value.first.return_value = mock_activity_history

        res = download_sentinel(input_args)

        # Must not be called since file already exists and its valid.
        mock_download_request.assert_not_called()

        assert type(res) == dict
        assert res['activity_type'] == 'correctionS2'
        assert res['args']['file'] == input_args['args']['file']

    # Mocking zip. The first validation must be invalid.
    @pytest.mark.parametrize('created', [False])
    @pytest.mark.parametrize('side_effect', [[True]])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_download_auto_retry(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_get_or_create):
        input_args = self.create_activity()
        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 202

        # Attaching input sceneid to the mock as property
        type(mock_activity_history.activity).sceneid = input_args['sceneid']

        # Mocking find RadcorActivityHistory
        query_property.return_value.filter.return_value.first.return_value = mock_activity_history

        with pytest.raises(HTTPError):
            download_sentinel(input_args)

    @pytest.mark.parametrize('created', [False])
    @pytest.mark.parametrize('side_effect', [[False]])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_download_from_onda(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_get_or_create, mock_credentials):
        input_args = self.create_activity()
        expected_link = input_args['args']['link']

        # Mocking 3rdparty
        type(mock_download_request.return_value).status_code = PropertyMock(side_effect=[202, 200])
        mock_download_request.return_value.json.return_value = dict(
            value=[
                dict(
                    id='$fakeId',
                    offline=False,
                    name='{}.zip'.format(input_args['sceneid'])
                )
            ]
        )
        # Attaching input sceneid to the mock as property
        type(mock_activity_history.activity).sceneid = input_args['sceneid']

        # Mocking find RadcorActivityHistory
        query_property.return_value.filter.return_value.first.return_value = mock_activity_history

        res = download_sentinel(input_args)

        assert mock_download_request.call_count == 3
        assert res['args']['file'] == input_args['args']['file']
