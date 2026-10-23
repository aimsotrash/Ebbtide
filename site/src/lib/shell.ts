/** A folder for the shell: plain paths as they are, anything else single-quoted, with ~/ left to expand. */
export function shellPath(path: string) {
  if (/^[\w~./-]+$/.test(path)) return path
  const quote = (text: string) => `'${text.replaceAll("'", "'\\''")}'`
  return path.startsWith('~/') ? `~/${quote(path.slice(2))}` : quote(path)
}
