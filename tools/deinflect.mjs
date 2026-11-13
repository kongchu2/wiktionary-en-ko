// What Yomitan's English deinflection makes of each word. Reads {words: [word], rules: {headword: [rule, ...]}}
// on stdin and prints {word: [[headword, [transform, ...]], ...]} for the headwords it reaches with a matching
// part of speech (years → year via "plural"). Used by `python -m enko translate order`.
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

// Derivations (previously → previous by "adverb", unhappy → happy by "un-") make a new word, not a form of the
// old one, so they are no reason to hide anything.
const DERIVATIONS = new Set(['adverb', '-y', 'un-', '-able']);
const {words, rules} = JSON.parse(readFileSync(0, 'utf8'));
const transformer = new MultiLanguageTransformer();
transformer.prepare();
const flags = new Map();
const flagsOf = (rule) => {
    if (!flags.has(rule)) { flags.set(rule, transformer.getConditionFlagsFromPartsOfSpeech('en', [rule])); }
    return flags.get(rule);
};
const out = {};
for (const word of words) {
    const found = [];
    for (const {text, trace, conditions} of transformer.transform('en', word)) {
        if (trace.length === 0 || text === word || !(text in rules)) { continue; }
        if (trace.some((f) => DERIVATIONS.has(f.transform))) { continue; }
        if (!rules[text].some((rule) => LanguageTransformer.conditionsMatch(conditions, flagsOf(rule)))) { continue; }
        if (!found.some(([t]) => t === text)) { found.push([text, trace.map((f) => f.transform).reverse()]); }
    }
    if (found.length > 0) { out[word] = found; }
}
console.log(JSON.stringify(out));
