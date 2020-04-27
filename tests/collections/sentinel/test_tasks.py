from unittest.mock import Mock, PropertyMock, patch, call
import pytest
from celery.exceptions import Retry
from requests.exceptions import HTTPError

# Initialize Celery worker
import bdc_collection_builder.celery.worker
from bdc_collection_builder.collections.sentinel.clients import sentinel_clients
from bdc_collection_builder.collections.sentinel.tasks import atm_correction, download_sentinel
from bdc_collection_builder.utils import initialize_factories, finalize_factories


def setup_module():
    initialize_factories()


def teardown_module():
    finalize_factories()


class TestSentinelTasks:
    @staticmethod
    def create_activity(activity_type='downloadS2'):
        return dict(
            activity_type='downloadS2',
            collection_id='FakeCollection',
            sceneid='S2A_MSIL1C_20000101T000000_N0000_R000_T00AAA_20000101T000000',
            args=dict(
                file='/tmp/',
                link='http://fake-link'
            )
        )

    def _mock_query_activity(scene_id, query_property, mock_activity_history):
        # Attaching input sceneid to the mock as property
        type(mock_activity_history.activity).sceneid = scene_id

        # Mocking find RadcorActivityHistory
        query_property.return_value.filter.return_value.first.return_value = mock_activity_history


    @pytest.mark.parametrize('side_effect', [[False, False]])
    @pytest.mark.parametrize('created', [False])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_download_copernicus(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_get_or_create, mock_open):
        input_args = self.create_activity()

        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 200
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

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
    @pytest.mark.parametrize('exists', [True])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_skip_download_zip_exists(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_os_path, mock_get_or_create):
        input_args = self.create_activity()

        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 200
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

        res = download_sentinel(input_args)

        # Must not be called since file already exists and its valid.
        mock_download_request.assert_not_called()

        assert type(res) == dict
        assert res['activity_type'] == 'correctionS2'
        assert res['args']['file'] == input_args['args']['file']

    # Mocking zip. The first validation must be invalid.
    @pytest.mark.parametrize('created', [False])
    @pytest.mark.parametrize('side_effect', [[True]])
    # @pytest.mark.parametrize('locked', [False])
    @patch('requests.get')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_download_auto_retry(self, query_property, mock_download_request, mock_activity_history, mock_zip_sentinel, mock_get_or_create):
        input_args = self.create_activity()
        # Mocking 3rdparty
        mock_download_request.return_value.status_code = 202
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

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
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

        res = download_sentinel(input_args)

        assert mock_download_request.call_count == 3
        assert res['args']['file'] == input_args['args']['file']

    @pytest.mark.parametrize('created', [False])
    @pytest.mark.parametrize('side_effect', [[False]])
    @patch('requests.get')
    @patch('requests.post')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_order_download_from_onda(self, query_property, mock_post, mock_get, mock_activity_history, mock_zip_sentinel, mock_get_or_create, mock_credentials):
        input_args = self.create_activity()

        # Mocking 3rdparty (the 3 request must fail)
        type(mock_get.return_value).status_code = PropertyMock(side_effect=[202, 200, 400])
        mock_get.return_value.raise_for_status.side_effect = [
            Mock(), # ignore search catalogue error
            HTTPError('Offline')
        ]
        type(mock_post.return_value).status_code = 200
        mock_get.return_value.json.return_value = dict(
            value=[
                dict(
                    id='$fakeId',
                    offline=True,
                    name='{}.zip'.format(input_args['sceneid'])
                )
            ]
        )
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

        # When ordering a product from ONDA Catalogue, it requires around
        # twenty minutes to be Online. In this way, a Retry is scheduled
        # TODO: Implement a fake restart in order to check if download is called
        with pytest.raises(HTTPError):
            download_sentinel(input_args)

        mock_post.assert_called()

    @pytest.mark.parametrize('created', [False])
    @pytest.mark.parametrize('side_effect', [[False]])
    @patch('bdc_db.models.base_sql.BaseModel.query')
    @patch('time.sleep')
    def test_wait_available_user(self, mock_time, query_property, mock_activity_history, mock_zip_sentinel, mock_get_or_create):
        SECRETS_BUSY_USERS = {
            "user": {"password": "pass", "count": 2}
        }

        # Override sentinel clients with busy users
        sentinel_clients._users = SECRETS_BUSY_USERS
        sentinel_clients.initialize()

        input_args = self.create_activity()

        # Assuming that when call sleep, raise error in order to
        # interrupt loop
        mock_time.side_effect = RuntimeError('')
        TestSentinelTasks._mock_query_activity(input_args['sceneid'], query_property, mock_activity_history)

        with pytest.raises(RuntimeError):
            download_sentinel(input_args)

        # ensure user is called
        mock_time.assert_any_call(5)


class TestSentinelCorrection:
    """Test sentinel surface reflectance correction."""

    @staticmethod
    def correction_activity():
        activity = TestSentinelTasks.create_activity('correctionS2')
        activity['args']['file'] = '{}2000-01/{}.SAFE'.format(activity['args']['file'], activity['sceneid'])

        return activity

    @patch('requests.get')
    @patch('pathlib.Path.mkdir')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_correction_sentinel(self, query_property, mock_path, mock_get, mock_activity_history):
        activity = TestSentinelCorrection.correction_activity()

        scene_id_without_processing = 'S2A_MSIL2A_20000101T000000_N9999_R000_T00AAA'

        expected_file_l2 = '/tmp/Repository/Archive/S2_MSI/2000-01/{}'.format(scene_id_without_processing)

        TestSentinelTasks._mock_query_activity(activity['sceneid'], query_property, mock_activity_history)
        type(mock_get.return_value).status_code = 200
        type(mock_get.return_value).content = '{"status": "SUCCESS"}'

        res = atm_correction(activity)

        mock_path.assert_called()
        mock_get.assert_called()
        assert res['activity_type'] == 'publishS2'
        assert res['args']['file'].endswith('.SAFE')
        assert expected_file_l2 in res['args']['file']

    @patch('shutil.rmtree')
    @patch('requests.get')
    @patch('pathlib.Path.mkdir')
    @patch('bdc_db.models.base_sql.BaseModel.query')
    def test_correction_sentinel_error(self, query_property, mock_path, mock_get, mock_rmtree, mock_activity_history):
        activity = TestSentinelCorrection.correction_activity()

        TestSentinelTasks._mock_query_activity(activity['sceneid'], query_property, mock_activity_history)
        type(mock_get.return_value).status_code = 400
        type(mock_get.return_value).content = '{"status": "ERROR"}'

        with pytest.raises(RuntimeError):
            atm_correction(activity)

        mock_rmtree.assert_called()
