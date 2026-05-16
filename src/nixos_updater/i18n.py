import gettext
from importlib.resources import as_file, files


def _load() -> gettext.NullTranslations:
    try:
        with as_file(files("nixos_updater").joinpath("locales")) as locale_dir:
            return gettext.translation("nixos-updater", localedir=str(locale_dir))
    except Exception:
        return gettext.NullTranslations()


_ = _load().gettext
