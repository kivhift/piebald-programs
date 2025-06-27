import abc
import io
import os
import pathlib
import tomllib
import warnings


class ConfigValidator(abc.ABC):
    def __init__(self, default=None):
        self.default = default

    def __set_name__(self, cls, name):
        self.name = name
        self.key = f'_{name}'

        _items = '_items'
        if not hasattr(cls, _items):
            setattr(cls, _items, set())

        getattr(cls, _items).add(name)

    def __get__(self, obj, cls):
        return getattr(obj, self.key, self.default)

    def __set__(self, obj, value):
        setattr(obj, self.key, self.validate(value))

    def __delete__(self, obj):
        if self.is_set(obj):
            delattr(obj, self.key)

    def is_set(self, obj):
        return hasattr(obj, self.key)

    @abc.abstractmethod
    def validate(self, value):
        pass


class Boolean(ConfigValidator):
    def __init__(self, default=False):
        super().__init__(default)

    def validate(self, value):
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            trues = ('1', 'yes', 'true')
            falses = ('0', 'no', 'false')
            lowered_value = value.lower()

            if lowered_value in trues:
                return True

            if lowered_value in falses:
                return False

            raise ValueError(
                f'Expected {value!r} to be in {trues} or {falses} for {self.name}'
            )

        raise ValueError(
            f'Expected {value!r} to be bool or boolean-like string for {self.name}'
        )


class FilePath(ConfigValidator):
    def validate(self, value):
        path = pathlib.Path(value)

        if path.exists() and not path.is_file():
            raise ValueError(f'Given path {value!r} is not a file for {self.name}')

        return path


class ConfigBase:
    def __str__(self):
        return '\n'.join(
            f'{name} = {getattr(self, name)}'
            for name in sorted(getattr(type(self), '_items', tuple()))
        )

    def is_set(self, name):
        cls = type(self)
        if name not in cls._items:
            raise ValueError(f'{name!r} is not a configuration item')

        return vars(cls)[name].is_set(self)

    def any_set(self, *names):
        return any(self.is_set(name) for name in names)

    @classmethod
    def environ(cls, key):
        return os.environ.get(f'{cls._env_tag.upper()}_{key.upper()}')

    @classmethod
    def load(cls, file=None, cmdline=None):
        cfg = cls.__new__(cls)

        items = getattr(cls, '_items', None)
        if items is None:
            return cfg

        if file is None:
            cfg_data = {}
        elif isinstance(file, (str, pathlib.Path)):
            with open(file, 'rb') as fin:
                cfg_data = tomllib.load(fin)
        else:
            cfg_data = tomllib.load(file)

        cmdline = cmdline or object()
        for key in items:
            try:
                if (val := getattr(cmdline, key, None)) is not None:
                    src = 'command line'
                    setattr(cfg, key, val)
                elif (val := cls.environ(key)) is not None:
                    src = 'environment variable'
                    setattr(cfg, key, val)
                elif (cfg_key := key.replace('_', '-')) in cfg_data:
                    src = 'configuration file'
                    setattr(cfg, key, cfg_data[cfg_key])
            except ValueError as e:
                raise ValueError(f'{e}, for {key} from {src}') from None

        if diff := set(cfg_data) - set(s.replace('_', '-') for s in items):
            warnings.warn(
                'Invalid items were specified in the configuration file: '
                f'{", ".join(sorted(diff))}',
                stacklevel=2,
            )

        return cfg

    @classmethod
    def loads(cls, cfgstr=None, cmdline=None):
        if cfgstr is None:
            return cls.load(cmdline=cmdline)

        return cls.load(file=io.BytesIO(cfgstr.encode()), cmdline=cmdline)


# To be able to explicitly give a value of False or True, you can use
# ``argparse.BooleanOptionalAction`` as the ``action`` argument when adding via
# ``add_argument()``.
