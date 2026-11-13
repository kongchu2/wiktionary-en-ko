// Sentence-initial words that Yomitan resolves to the wrong capitalised entry: "This" → Thi (a surname, by the
// plural rule) ranks above "this", because a deinflection with no text processing beats a lowercased exact
// match. Reads {words: [lowercase word], entries: {capitalised headword: [rule, ...]}} on stdin and prints
// the lowercase words whose capitalised form needs a link row ("This" → this). Used by `python -m enko select`.
import {existsSync, readFileSync} from 'node:fs';
import {registerHooks} from 'node:module';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const STUBS = 'export const convertVariants = (x) => x; export const Hangul = {}; export default {};';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const yomitan = process.env.YOMITAN_DIR || join(root, 'data', 'yomitan');
registerHooks({
    resolve(specifier, context, nextResolve) {
        if (/\/lib\/[\w.-]+\.js$/.test(specifier) && !existsSync(new URL(specifier, context.parentURL))) {
            return {url: 'data:text/javascript,' + encodeURIComponent(STUBS), shortCircuit: true};
        }
        return nextResolve(specifier, context);
    },
});
const load = (path) => import(pathToFileURL(join(yomitan, path)).href);
const {MultiLanguageTransformer} = await load('ext/js/language/multi-language-transformer.js');
const {LanguageTransformer} = await load('ext/js/language/language-transformer.js');

const {words, entries} = JSON.parse(readFileSync(0, 'utf8'));
const transformer = new MultiLanguageTransformer();
transformer.prepare();
const flags = (rule) => transformer.getConditionFlagsFromPartsOfSpeech('en', [rule]);
const out = [];
for (const word of words) {
    const capital = word[0].toUpperCase() + word.slice(1);
    if (capital === word || capital in entries) { continue; }
    const hijacked = transformer.transform('en', capital).some(({text, trace, conditions}) => (
        trace.length > 0 && text !== capital && text in entries &&
        entries[text].some((rule) => LanguageTransformer.conditionsMatch(conditions, flags(rule)))
    ));
    if (hijacked) { out.push(word); }
}
console.log(JSON.stringify(out));
