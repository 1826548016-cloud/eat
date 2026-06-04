from django.apps import AppConfig


class StoreConfig(AppConfig):
    name = 'store'
    verbose_name = '干饭情报'

    def ready(self):
        import store.signals  # noqa: F401
