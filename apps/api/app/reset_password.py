"""Reset a member's password from the host (`./fm passwd <email>`).

The application has no email, so there is no reset-by-link. An owner resets other
members from the UI; when the *owner's* own password is lost, the only remaining
authority is shell access to the server — which is exactly this.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.db import session_scope
from app.models.household import User
from app.services import auth


def main() -> None:
    parser = argparse.ArgumentParser(description="Define uma nova palavra-passe para um membro.")
    parser.add_argument("email", help="Email do membro.")
    parser.add_argument(
        "--password",
        help="Nova palavra-passe. Sem esta opção é pedida de forma interativa.",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Nova palavra-passe: ")
    if len(password) < 8:
        sys.exit("A palavra-passe tem de ter pelo menos 8 caracteres.")

    with session_scope() as db:
        user = db.scalar(
            select(User).where(User.email == args.email.strip().lower(), User.is_deleted.is_(False))
        )
        if user is None:
            sys.exit(f"Não existe nenhum membro com o email {args.email}.")
        if user.is_dependent:
            sys.exit("Um dependente não tem palavra-passe.")

        # Same path the UI takes: rehash and drop every open session.
        auth.change_password(db, user, password)
        print(f"Palavra-passe de {user.display_name} ({user.email}) alterada.")
        print("Todas as sessões abertas desse membro foram terminadas.")


if __name__ == "__main__":
    main()
