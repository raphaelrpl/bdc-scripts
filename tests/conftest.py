from unittest.mock import Mock, create_autospec, patch
import pytest
from bdc_db.models import CollectionItem
from bdc_collection_builder import create_app
from bdc_collection_builder.collections.models import RadcorActivityHistory



DEFAULT_SECRETS = '''{
    "sentinel": {
        "user": {"password": "pass", "count": 0}
    }
}'''


@pytest.fixture(scope='class')
def app():
    _app = create_app('TestingConfig')

    context = _app.app_context()
    context.push()

    yield

    context.pop()


@pytest.fixture()
def mock_redis():
    with patch('redis.Redis.from_url') as mocked:
        mocked.return_value.get.return_value = DEFAULT_SECRETS
        yield mocked


@pytest.fixture()
def mock_redis_lock(mock_redis, locked):
    mock_lock = Mock()
    mock_lock.locked.return_value = locked
    mock_lock.acquire.return_value = None

    mock_redis.return_value.lock.return_value = mock_lock

    yield mock_lock


@pytest.fixture(scope='class')
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='class')
def mock_open():
    with patch('builtins.open') as mocked:
        yield mocked


@pytest.fixture()
def mock_os_path(exists):
    with patch('os.path.exists', return_value=exists) as mocked:
        yield mocked


@pytest.fixture()
def mock_credentials(mock_open):
    mock_open.return_value.__enter__.return_value.read.return_value = '''
        {
            "landsat": {
                "username": "fake",
                "password": "fake"
            },
            "sentinel": {
                "fake": {
                    "password": "fake",
                    "count": 0
                }
            },
            "creodias": {
                "username": "user",
                "password": "pass"
            },
            "onda": {
                "username": "email",
                "password": "pass"
            }
        }
    '''


class MockZip:
    """Define mock abstraction for a ZipFile."""

    def __init__(self, *args):
        self.files = [Mock(filename='S2A_MSIL1C_20000101T000000_N0000_R000_T00AAA_20000101T000000.SAFE/')]

    def __iter__(self):
        return iter(self.files)

    def __enter__(self):
        return self

    def testzip():
        return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        return True

    def namelist(self):
        return [info.filename for info in self.files]


@pytest.fixture()
def mock_zip_sentinel(side_effect):
    """Create a mock for handling ZipFiles."""
    with patch('bdc_collection_builder.collections.utils.ZipFile', return_value=True) as mocked:
        zip_archive = Mock()
        zip_mocked_read = Mock()
        zip_archive.return_value.read = zip_mocked_read

        zip_archive.testzip.side_effect = side_effect

        mocked.return_value = zip_archive
        mocked.return_value.__enter__ = MockZip
        mocked.return_value.__exit__ = zip_archive
        yield mocked


@pytest.fixture()
def mock_activity_history():
    """Create a mock for Collection Builder Activity Execution."""
    activity_history_mock = create_autospec(RadcorActivityHistory)
    activity_mock = Mock()

    # Mocking 3rdparty
    mock_item = create_autospec(CollectionItem)

    type(activity_history_mock).activity = activity_mock

    yield activity_history_mock


@pytest.fixture()
def mock_get_or_create(created):
    mock_item = create_autospec(CollectionItem)

    with patch('bdc_collection_builder.collections.base_task.get_or_create_model', return_value=[mock_item, created]) as mocked:
        yield mocked


@pytest.fixture(scope='class')
def patcher():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()
