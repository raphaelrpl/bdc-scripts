from json import JSONDecodeError
import pytest

from bdc_collection_builder.collections.sentinel.clients import UserClients
from bdc_collection_builder.utils import initialize_factories, finalize_factories


DEFAULT_SECRETS = {
    "user": {"password": "pass", "count": 0}
}


def setup_module():
    initialize_factories()


def teardown_module():
    finalize_factories()


class TestSentinelClients:
    @pytest.mark.parametrize('exists', [True])
    def test_get_available_user(self, mock_os_path):
        clients = UserClients()
        clients._users = DEFAULT_SECRETS
        clients.initialize()

        user = clients.use()

        assert user != None
        assert user.username == 'user' and user.password == 'pass'

    @pytest.mark.parametrize('exists', [True])
    def test_get_user_none(self, mock_os_path):
        clients = UserClients()
        clients._users = DEFAULT_SECRETS
        clients.initialize()

        # Sentinel user do two-requests max
        user = clients.use()
        user2 = clients.use()

        assert user != None and user2 != None

        none_user = clients.use()

        assert none_user == None


    @pytest.mark.parametrize('exists', [False])
    def test_raise_error_when_secrets_not_exists(self, mock_os_path):
        with pytest.raises(FileNotFoundError):
            UserClients()

    @pytest.mark.parametrize('exists', [True])
    def test_raise_error_when_secrets_invalid(self, mock_os_path, mock_open):
        mock_open.return_value.__enter__.return_value.read.return_value = 'Not a JSON'

        with pytest.raises(JSONDecodeError):
            UserClients()

    @pytest.mark.parametrize('exists', [True])
    def test_raise_error_when_sentinel_is_not_set(self, mock_os_path, mock_open):
        mock_open.return_value.__enter__.return_value.read.return_value = '{}'

        with pytest.raises(RuntimeError):
            UserClients()