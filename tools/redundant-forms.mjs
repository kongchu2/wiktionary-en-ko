// Which form links does Yomitan not need? Reads {forms: [{w, to, rule}], rules: {headword: [rule, ...]}} on
// stdin and prints the indexes of the forms that Yomitan's own English deinflection already resolves to an
// entry of the right part of speech (plans → plan, picked up → pick up). Used by `python -m enko select`.
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

const {forms, rules} = JSON.parse(readFileSync(0, 'utf8'));
const transformer = new MultiLanguageTransformer();
transformer.prepare();
const flags = new Map();
const flagsOf = (rule) => {
    if (!flags.has(rule)) { flags.set(rule, transformer.getConditionFlagsFromPartsOfSpeech('en', [rule])); }
    return flags.get(rule);
};
const cache = new Map();
const redundant = [];
forms.forEach(({w, to, rule}, index) => {
    if (!rule || !(rules[to] || []).includes(rule)) { return; }
    if (!cache.has(w)) { cache.set(w, transformer.transform('en', w)); }
    const wanted = flagsOf(rule);
    if (cache.get(w).some((r) => r.text === to && r.trace.length > 0 && LanguageTransformer.conditionsMatch(r.conditions, wanted))) {
        redundant.push(index);
    }
});
console.log(JSON.stringify(redundant));
