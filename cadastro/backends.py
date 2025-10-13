# cadastro/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

def only_digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

class CPFOrUsernameBackend(ModelBackend):
    """
    Permite login com CPF (11 dígitos) OU com username.
    - Remove pontuação do CPF.
    - Mantém todas as verificações padrão (senha, is_active, etc).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if not username or not password:
            return None

        candidate = str(username).strip()
        cpf = only_digits(candidate)

        user = None
        try:
            if len(cpf) == 11:
                # tenta por CPF
                user = User.objects.get(cpf=cpf)
            else:
                # tenta por username (padrão)
                user = User.objects.get(**{User.USERNAME_FIELD: candidate})
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
