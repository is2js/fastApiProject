from sqlalchemy import inspect


class ReprMixin:
    __abstract__ = True

    __repr_attrs__ = []
    __repr_max_length__ = 10

    def __repr__(self):
        info: str = f"<{self.__class__.__name__}" \
                    f"#{self._id_str}"
        info += f" {self._repr_attrs_str}" if self.__repr_attrs__ else ""
        info += ">"
        return info

    # id -> string
    @property
    def _id_str(self):
        _ids = inspect(self).identity  # 생성객체라면 id없어서 None 반환 / 있으면 (1, ) tuple
        if not _ids:
            return 'None'
        return '-'.join([str(_id) for _id in _ids]) if len(_ids) > 1 else str(_ids[0])

    # id 외 __repr_attrs__에 표시한 칼럼 -> string
    @property
    def _repr_attrs_str(self):
        max_length = self.__repr_max_length__

        values = []
        # 1) 표시할게 1개라면,
        single = len(self.__repr_attrs__) == 1
        for key in self.__repr_attrs__:
            if not hasattr(self, key):
                raise KeyError(f"Invalid attribute '{key}' in __repr__attrs__ of {self.__class__}")
            value = getattr(self, key)

            value = str(value)
            if len(value) > max_length:
                value = value[:max_length] + '...'

            values.append(f"{value!r}" if single else f"{key}:{value}")

        return ' '.join(values)