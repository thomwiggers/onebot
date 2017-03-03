# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.acl` Access Control plugin
================================================

This plugin implements advanced access control for the bot.
It uses the :mod:`onebot.plugins.users` plugin to store access control
settings with each user.
"""

import asyncio

import irc3
from irc3.plugins.command import command


class user_based_policy(object):
    """Policy to allow access based on permissions stored in users

    Depends on the :mod:`onebot.plugins.users` plugin.

    Needs to be set as the :mod:`irc3.plugins.guard` ``mask`` option.
    """

    def __init__(self, bot):
        self.bot = bot
        self.bot.include('onebot.plugins.users')
        self.log = self.bot.log.getChild(__name__)

    def has_permission(self, mask, permission):
        """
        Returns if the user identified by ``mask`` has ``permission``
        """
        user = self.bot.get_user(mask.nick)
        perms = []
        if user:
            perms = yield from user.get_setting('permissions', set())

        self.log.debug("Found permissions for %s: %r", mask.nick, perms)

        if 'ignore' in perms and permission is None:
            return False

        if (permission is None or
                permission in perms or
                'all_permissions' in perms):
            return True

        return False

    @asyncio.coroutine
    def __call__(self, predicates, meth, client, target, args, **kwargs):
        permitted = yield from self.has_permission(
            client, predicates.get('permission'))
        if permitted:
            if asyncio.iscoroutinefunction(meth):
                yield from meth(client, target, args)
                return
            else:
                return meth(client, target, args)
        cmd_name = predicates.get('name', meth.__name__)
        self.log.info('Denied access to command %s to user %s',
                      cmd_name, client)
        self.bot.privmsg(
            client.nick,
            'You are not allowed to use the {command} command'.format(
                command=cmd_name))


@irc3.plugin
class ACLPlugin(object):
    """Plugin to provide access control moderation

    Depends on the :mod:`irc3.plugins.command`, :mod:`irc3.plugins.storage`
    and the `onebot.plugins.users` plugins.

    Configuration settings:
        - ``superadmin``: username to store in the database with
          `all_permissions`. username depends on mask chosen
    """

    requires = [
        'irc3.plugins.command',
        'onebot.plugins.users',
        'irc3.plugins.storage',
    ]

    available_permissions = [
        'operator',
        'admin',
        'wiki',
        'view',
        'ignore'
    ]

    def __init__(self, bot):
        self.bot = bot
        module = self.__class__.__module__
        self.log = bot.log.getChild(module)
        self.config = bot.config.get(module, {})
        self.log.debug('Config: %r', self.config)
        if 'superadmin' in self.config:
            self.log.info("Giving {} all_permissions".format(
                self.config['superadmin']))
            self.bot.db.set(self.config['superadmin'],
                            permissions=['all_permissions'])

    @command(permission='admin', show_in_help_list=False)
    @asyncio.coroutine
    def acl(self, mask, target, args):
        """Administrate the ACL

            %%acl (add | remove) <user> <permission>
            %%acl --by-id (add | remove) <id> <permission>
        """
        username, permission = args['<user>'], args['<permission>']
        if permission not in self.available_permissions:
            self.bot.privmsg(
                target,
                ('Invalid permission level. Available permissions: '
                 '{permissions}'.format(
                     permissions=', '.join(self.available_permissions))))
            return

        if not args['--by-id']:
            user = self.bot.get_user(username)
            if not user:
                self.bot.privmsg(
                    target, ("I don't know {user}. "
                             "Please use --by-id".format(user=username)))
                return
            current_permissions = yield from user.get_setting(
                'permissions', [])
        else:
            current_permissions = self.bot.db.get(args['<id>'], {}).get(
                'permissions', [])

        if args['add'] and permission not in current_permissions:
            current_permissions.append(permission)
        elif args['remove'] and permission in current_permissions:
            current_permissions.remove(permission)

        if not args['--by-id']:
            user.set_setting('permissions', current_permissions)
        else:
            if args['<id>'] not in self.bot.db:
                self.bot.db[args['<id>']] = {}
            self.bot.db[args['<id>']]['permissions'] = (
                current_permissions)

        self.bot.privmsg(target, 'Updated permissions for {user}'.format(
            user=username or args['<id>']))

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
