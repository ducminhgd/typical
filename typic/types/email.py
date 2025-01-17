#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import re
from typing import ClassVar, Pattern, Match, Optional
from urllib.parse import quote

from typic.util import cached_property, slotted
from .url import (
    NetworkAddress,
    PRIVATE_HOSTS,
    INTERNAL_HOSTS,
    INTERNAL_IP_PATTERN,
    NetworkAddressValueError,
)

__all__ = ("Email", "EmailAddrInfo", "EMAIL_PATTERN", "EmailValueError")


class EmailValueError(NetworkAddressValueError):
    """A generic error for when we've received an invalid value for an email."""

    pass


# http://emailregex.com/
# https://help.returnpath.com/hc/en-us/articles/220560587-What-are-the-rules-for-email-address-syntax-
# expanding a bit for more specific detection
# also violating DRY :'( by copying the host regex from URL,
# but hey, this means we're more compliant with RFC 5322,
# AND our regex is readable, and readability counts!
EMAIL_PATTERN = re.compile(
    r"""
    (
        ^
        ((?P<name>([A-Z]+\s?)+)\s<)?
        # user
        (?P<username>([A-Z0-9]([!#$%&'*=?^`{|_.+-])?)*[A-Z0-9]+)
        @
        # host
        (?P<host>(?:
        # Domain
            (?P<domain>
                (?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+
                (?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)
            )
            # Localhost
            |(?P<localhost>localhost)
            |(?P<dotless>(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.?))
            # IPV4
            |(?P<ipv4>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})
            # IPV6
            |(?P<ipv6>\[[A-F0-9]*:[A-F0-9:]+\])
        ))
        (>)?
        $
    )
    """,
    re.I | re.VERBOSE,
)


@slotted
@dataclasses.dataclass(frozen=True)
class EmailAddrInfo:
    """Detailed information about an email address.

    Can be called directly, generated by casting a :py:class:`str` as :py:class:`Email`,
    or created with :py:meth:`EmailAddrInfo.from_str`

    Notes
    -----
    An email address is also, technically, a network address. However, it has some more
    constraints and we're interested in only a specific amount of information.
    """

    PATTERN: ClassVar[Pattern] = EMAIL_PATTERN
    """The raw match from paring the provided string."""
    name: str
    """The proper name associated to the email."""
    username: str
    """The username portion of the email."""
    host: str
    """The host address where the email server is located."""
    is_ip: bool = False

    @classmethod
    def from_str(cls, value) -> "EmailAddrInfo":
        """Parse & validate a string, generate an instance of :py:class:`EmailAddrInfo`."""
        match: Optional[Match] = cls.PATTERN.match(value)
        if not match or not value:
            err_msg = f"<{value!r}> is not a valid email address."
            raise EmailValueError(err_msg) from None
        return cls(
            name=(match["name"] or "").rstrip(),
            username=match["username"],
            host=match["host"],
            is_ip=bool(match["ipv4"] or match["ipv6"]),
        )

    @cached_property
    def address(self) -> str:
        """The fully-qualified email address.

        If this instance was generated from a string, it will match.
        """
        name = f"{self.name} <" if self.name else ""
        address = f"{self.username}@{self.host}"
        return f"{name}{address}>" if name else address

    @cached_property
    def address_encoded(self) -> str:
        """The fully-qualified email address, encoded."""
        name = f"{self.name} <" if self.name else ""
        address = quote(f"{self.username}@{self.host}")
        return f"{name}{address}>" if name else address

    @cached_property
    def is_named(self) -> bool:
        """Whether or not this email is 'named' (or 'pretty')

        i.e.: `<Foo foo@bar.com>`
        """
        return bool(self.name)

    @cached_property
    def is_private(self) -> bool:
        """Whether or not the host in the email is a private IP, i.e., 'localhost'."""
        return self.host in PRIVATE_HOSTS

    @cached_property
    def is_internal(self) -> bool:
        """Whether or not the host in the email is an internal address.

        Internal DNS/IP addresses aren't necessarily private, hence the differentiation.
        """
        return bool(
            self.host in INTERNAL_HOSTS
            or (self.is_ip and INTERNAL_IP_PATTERN.match(self.host))
        )


# Deepcopy is broken for frozen dataclasses with slots.
# https://github.com/python/cpython/pull/17254
# EmailAddrInfo.__slots__ = tuple(_.name for _ in dataclasses.fields(EmailAddrInfo))


class Email(NetworkAddress):
    """An immutable email address. Supports 'pretty' and 'raw', i.e.:

        `Foo Bar <foo.bar@foobar.net>`
        `foo.bar@foobar.net`

    Detailed information about the email string can be found up via :py:attr:`Email.info`.

    Examples
    --------
    >>> import typic
    >>> email = typic.Email("Foo Bar <foo.bar@foobar.net>")
    >>> print(email)
    Foo Bar <foo.bar@foobar.net>
    >>> email.info.host
    'foobar.net'
    >>> email.info.is_named
    True
    >>> import json
    >>> json.dumps([email])
    '["Foo Bar <foo.bar@foobar.net>"]'

    See Also
    --------
    :py:class:`EmailAddrInfo`

    Notes
    -----
    This object inherits from :py:class:`str` and so is natively JSON-serializable.
    """

    @cached_property
    def info(self) -> EmailAddrInfo:  # type: ignore
        """Get detailed information about your email string.

        See Also
        --------
        :py:class:`EmailAddrInfo`
        """

        return EmailAddrInfo.from_str(self)
