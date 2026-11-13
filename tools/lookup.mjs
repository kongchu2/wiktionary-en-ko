// Look words up the way Yomitan does: its real translator (deinflection, capitalisation, longest match,
// result order) run against the built zip, with the dictionary database replaced by an in-memory map.
//
//   node tools/lookup.mjs went "fell in love"          one lookup per argument
//   node tools/lookup.mjs --text article.txt           scan a text word by word, report what is not found
//   options: --json, --word (search resolution "word" instead of "letter"), --scan N (scan length, default 16)
//
// Needs a checkout of https://github.com/yomidevs/yomitan in data/yomitan (or YOMITAN_DIR).
import {execFileSync} from 'node:child_process';
import {existsSync, readFileSync} from 'node:fs';
import {registerHooks} from 'node:module';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const STUBS = 'export const convertVariants = (x) => x; export const Hangul = {}; export default {};';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const yomitan = process.env.YOMITAN_DIR || join(root, 'data', 'yomitan');
const zip = join(root, 'dist', 'wiktionary-en-ko.zip');
// Yomitan bundles a few npm libraries into ext/lib at build time (kanji variants, Hangul, kana). English lookups
// never call them, so a checkout without `npm ci` gets empty stand-ins.
registerHooks({
    resolve(specifier, context, nextResolve) {
        if (/\/lib\/[\w.-]+\.js$/.test(specifier) && !existsSync(new URL(specifier, context.parentURL))) {
            return {url: 'data:text/javascript,' + encodeURIComponent(STUBS), shortCircuit: true};
        }
        return nextResolve(specifier, context);
    },
});
const {Translator} = await import(pathToFileURL(join(yomitan, 'ext/js/language/translator.js')).href);

const unzip = (name) => execFileSync('unzip', ['-p', zip, name], {maxBuffer: 1 << 30, encoding: 'utf8'});
const title = JSON.parse(unzip('index.json')).title;
const split = (s) => (s.length > 0 ? s.split(' ') : []);

/** The part of Yomitan's DictionaryDatabase that the translator calls. */
class Database {
    constructor() {
        this.byTerm = new Map();
        this.bySequence = new Map();
        let id = 0;
        const names = execFileSync('unzip', ['-Z1', zip], {encoding: 'utf8'}).split('\n').filter((n) => /^term_bank_\d+\.json$/.test(n));
        for (const name of names) {
            for (const [expression, reading, definitionTags, rules, score, glossary, sequence, termTags] of JSON.parse(unzip(name))) {
                const row = {id: ++id, expression, reading: reading || expression, definitionTags, rules, score, glossary, sequence, termTags};
                for (const [map, key] of [[this.byTerm, expression], [this.bySequence, sequence]]) {
                    if (!map.has(key)) { map.set(key, []); }
                    map.get(key).push(row);
                }
            }
        }
        this.rows = id;
    }

    _term(matchSource, row, index) {
        return {
            index, matchType: 'exact', matchSource, term: row.expression, reading: row.reading,
            definitionTags: split(row.definitionTags), termTags: split(row.termTags), rules: split(row.rules),
            definitions: row.glossary, score: row.score, dictionary: title, id: row.id, sequence: row.sequence,
        };
    }

    async findTermsBulk(terms) { return terms.flatMap((t, i) => (this.byTerm.get(t) || []).map((row) => this._term('term', row, i))); }
    async findTermsExactBulk(items) { return items.flatMap(({term, reading}, i) => (this.byTerm.get(term) || []).filter((row) => row.reading === reading).map((row) => this._term('term', row, i))); }
    async findTermsBySequenceBulk(items) { return items.flatMap(({query}, i) => (this.bySequence.get(query) || []).map((row) => this._term('sequence', row, i))); }
    async findTermMetaBulk() { return []; }
    async findTagMetaBulk(items) { return items.map(() => void 0); }
    async getDictionaryInfo() { return []; }
}

const args = process.argv.slice(2);
const flag = (name) => { const i = args.indexOf(name); if (i < 0) { return false; } args.splice(i, 1); return true; };
const value = (name, fallback) => { const i = args.indexOf(name); if (i < 0) { return fallback; } return args.splice(i, 2)[1]; };
const json = flag('--json');
const searchResolution = flag('--word') ? 'word' : 'letter';
const scanLength = Number(value('--scan', 16));
const textFile = value('--text', null);

const database = new Database();
const translator = new Translator(database);
translator.prepare();
const options = {
    matchType: 'exact', deinflect: true, primaryReading: '', mainDictionary: title,
    sortFrequencyDictionary: null, sortFrequencyDictionaryOrder: 'descending', removeNonJapaneseCharacters: false,
    textReplacements: [null], excludeDictionaryDefinitions: null, searchResolution, language: 'en', useAllFrequencyDictionaries: false,
    enabledDictionaryMap: new Map([[title, {index: 0, alias: title, allowSecondarySearches: false, partsOfSpeechFilter: true, useDeinflections: true}]]),
};

/** Korean glosses and the part-of-speech label from one structured-content definition. */
function gloss(node, out = {pos: '', ko: [], en: []}, inEnglish = false) {
    if (Array.isArray(node)) {
        for (const child of node) { gloss(child, out, inEnglish); }
    } else if (typeof node === 'string') {
        if (inEnglish) { out.en.push(node); }
    } else if (node && typeof node === 'object') {
        if (node.tag === 'summary') { return out; }
        inEnglish = inEnglish || (node.lang === 'en' && node.tag === 'ol');
        if (node.lang === 'ko' && typeof node.content === 'string') { out.ko.push(node.content); }
        if (!out.pos && node.data?.enko === 'tag' && !node.data.kind && typeof node.content === 'string') { out.pos = node.content; }
        gloss(node.content, out, inEnglish);
    }
    return out;
}

async function lookup(text) {
    const {dictionaryEntries, originalTextLength} = await translator.findTerms('group', text.slice(0, scanLength), options);
    return {
        matched: text.slice(0, originalTextLength),
        entries: dictionaryEntries.map((entry) => ({
            term: entry.headwords[0].term,
            from: entry.headwords[0].sources[0].originalText,
            rules: entry.inflectionRuleChainCandidates.map((c) => c.inflectionRules.map((r) => r.name).join(' > ')).filter(Boolean),
            senses: entry.definitions.map((d) => gloss(d.entries)),
        })),
    };
}

if (textFile === null) {
    const results = [];
    for (const query of args) {
        const result = await lookup(query);
        results.push({query, ...result});
        if (json) { continue; }
        console.log(`\n■ ${query}` + (result.entries.length > 0 ? '' : '  → 결과 없음'));
        for (const e of result.entries) {
            console.log(`  ${e.term}` + (e.from === e.term ? '' : `  ← ${e.from}`) + (e.rules.length > 0 ? `  (${e.rules.join(' | ')})` : ''));
            for (const s of e.senses) { console.log(`    [${s.pos}] ${s.ko.join(' / ').slice(0, 200)}`); }
        }
    }
    if (json) { console.log(JSON.stringify(results)); }
} else {
    // Hover every word of the text in turn, as a reader would, and keep the first (top) result.
    const text = readFileSync(textFile, 'utf8');
    const hits = [];
    const missing = new Map();
    for (const m of text.matchAll(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)) {
        const result = await lookup(text.slice(m.index).replace(/\s+/g, ' '));
        const top = result.entries[0];
        if (top) {
            hits.push({word: m[0], matched: result.matched, term: top.term, rules: top.rules, pos: top.senses[0]?.pos ?? '', ko: top.senses[0]?.ko[0] ?? '', en: top.senses[0]?.en[0] ?? ''});
        } else {
            missing.set(m[0], (missing.get(m[0]) || 0) + 1);
        }
    }
    const total = hits.length + [...missing.values()].reduce((a, b) => a + b, 0);
    if (json) {
        console.log(JSON.stringify({total, found: hits.length, missing: [...missing], hits}));
    } else {
        console.log(`단어 ${total}개 중 ${hits.length}개 조회됨 (${(100 * hits.length / total).toFixed(1)}%)`);
        console.log(`안 나온 것 (${missing.size}종): ` + [...missing].sort((a, b) => b[1] - a[1]).map(([w, n]) => (n > 1 ? `${w}×${n}` : w)).join(', '));
        for (const h of hits) { console.log(`${h.word}\t${h.matched === h.word ? '' : '[' + h.matched + '] '}${h.term}${h.rules.length > 0 ? ' (' + h.rules[0] + ')' : ''}\t${h.ko.slice(0, 60)}`); }
    }
}
