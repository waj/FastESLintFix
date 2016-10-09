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
    env = os.environ.copy()
    env["NODE_PATH"] = folder + "/node_modules"
    server_cmd = ["node", PLUGIN_PATH + "/eslint_server.js"]

    self.proc = subprocess.Popen(server_cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE, env = env, cwd = folder)
    print("Created " + str(self.proc.pid))
    self.port = int(self.proc.stdout.readline())

  def close(self):
    print("Killing " + str(self.proc.pid))
    self.proc.kill()

  def execute(self, text):
    conn = http.client.HTTPConnection("localhost", self.port)
    conn.request("POST", "/", text)
    body = conn.getresponse().read().decode('UTF-8')
    return json.loads(body)

def server_for_folder(folder):
  if folder not in servers:
    print("Not found for " + folder)
    servers[folder] = EslintServer(folder)

  return servers[folder]

class FastEslintFormatCommand(sublime_plugin.TextCommand):
  def is_enabled(self):
    caret = self.view.sel()[0].a
    syntax_name = self.view.scope_name(caret)
    return "source.js" in syntax_name

  def run(self, edit):
    vsize = self.view.size()
    region = sublime.Region(0, vsize)
    src = self.view.substr(region)
    folder = self.view.window().folders()[0]

    server = server_for_folder(folder)
    messages = server.execute(src)

    offset = 0
    for msg in messages:
      if 'fix' in msg:
        fix = msg['fix']
        region = sublime.Region(fix['range'][0] + offset, fix['range'][1] + offset)
        offset += len(fix['text']) - (fix['range'][1] - fix['range'][0])
        self.view.replace(edit, region, fix['text'])

class FastEslintFixEventListener(sublime_plugin.EventListener):
  @staticmethod
  def on_pre_save(view):
    cmd, args, repeat = view.command_history(1)
    if cmd == '':
      view.run_command('fast_eslint_format')
