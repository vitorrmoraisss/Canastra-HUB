import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CampusPasswordValidator:
    """
    Política de senhas definida pela CGTI:
    - mínimo de 12 caracteres;
    - pelo menos uma letra maiúscula;
    - pelo menos uma letra minúscula;
    - pelo menos dois caracteres especiais.
    """

    def validate(self, password, user=None):
        errors = []

        if len(password) < 12:
            errors.append(
                _("A senha deve conter pelo menos 12 caracteres.")
            )

        if not re.search(r"[A-Z]", password):
            errors.append(
                _("A senha deve conter pelo menos uma letra maiúscula.")
            )

        if not re.search(r"[a-z]", password):
            errors.append(
                _("A senha deve conter pelo menos uma letra minúscula.")
            )

        special_characters = re.findall(r"[^A-Za-z0-9\s]", password)
        if len(special_characters) < 2:
            errors.append(
                _("A senha deve conter pelo menos dois caracteres especiais.")
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "A senha deve conter pelo menos 12 caracteres, uma letra "
            "maiúscula, uma letra minúscula e dois caracteres especiais."
        )