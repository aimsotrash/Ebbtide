/// <reference types="node" />
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { shellPath } from './shell.ts'

test('folders reach the shell intact', () => {
  assert.equal(shellPath('~/code/Engram'), '~/code/Engram')
  assert.equal(shellPath('~/My Code/Engram'), "~/'My Code/Engram'")
  assert.equal(shellPath("/tmp/it's here"), "'/tmp/it'\\''s here'")
  assert.equal(shellPath('~/x; rm -rf ~'), "~/'x; rm -rf ~'")
})
