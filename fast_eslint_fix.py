import sublime
import sublime_plugin
import subprocess
import os
from os.path import dirname, realpath
import http.client
import json

PLUGIN_PATH = dirname(realpath(__file__))
servers = {}

def plugin_unloaded():
  for server in servers.values():
    server.close()

class EslintServer:
  def __init__(self, folder):
    self.folder = folder
    env = os.environ.copy()
    if "NODE_PATH" in env:
      env["NODE_PATH"] = folder + "/node_modules:" + env["NODE_PATH"]
    else:
      env["NODE_PATH"] = folder + "/node_modules"

    server_cmd = ["node", PLUGIN_PATH + "/eslint_server.js"]

    self.proc = subprocess.Popen(server_cmd, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, env = env, cwd = folder)
    self.port = int(self.proc.stdout.readline())
    print("Started ESLint server (pid: %d, port: %d)" % (self.proc.pid, self.port))

  def close(self):
    print("Killing ESLint server (pid: %d)" % self.proc.pid)
    self.proc.kill()

  def execute(self, text):
    try:
      conn = http.client.HTTPConnection("localhost", self.port)
      conn.request("POST", "/", text)
      body = conn.getresponse().read().decode('UTF-8')
      conn.close()
      return json.loads(body)
    except:
      del servers[self.folder]
      raise


def server_for_folder(folder):
  if folder not in servers:
    print("ESLint server not found for directory " + folder)
    servers[folder] = EslintServer(folder)

  return servers[folder]

class FastEslintFormatCommand(sublime_plugin.TextCommand):
  def is_enabled(self):
    caret = self.view.sel()[0].a
    syntax_name = self.view.scope_name(caret)
    return "source.js" in syntax_name

  def run(self, edit):
    folder = self.view.window().folders()[0]
    server = server_for_folder(folder)

    # Loop at most 10 times, until there are no more fixes to apply
    # This algorithm is inspired in the one present in `eslint` itself
    for _ in range(10):
      vsize = self.view.size()
      region = sublime.Region(0, vsize)
      src = self.view.substr(region)

      try:
        # Find only the messages that have something to fix
        fixes = [msg['fix'] for msg in server.execute(src) if 'fix' in msg]
        if len(fixes) == 0:
          break

        # Sort backwards
        fixes = sorted(fixes, key = lambda msg: (msg['range'][1], msg['range'][0]), reverse = True)
        last_fix_pos = len(src) + 1

        for fix in fixes:
          # Don't apply the fix if it overlaps with another one
          if fix['range'][1] >= last_fix_pos:
            continue
          last_fix_pos = fix['range'][0]

          # Apply the fix in the view
          region = sublime.Region(fix['range'][0], fix['range'][1])
          self.view.replace(edit, region, fix['text'])

      except Exception as e:
        sublime.error_message("Error while formatting the file: " + e.strerror)

class FastEslintFixEventListener(sublime_plugin.EventListener):
  @staticmethod
  def on_pre_save(view):
    cmd, args, repeat = view.command_history(1)
    if cmd == '':
      view.run_command('fast_eslint_format')
