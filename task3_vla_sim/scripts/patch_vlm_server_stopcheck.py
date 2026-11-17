"""Create vlm_server_stopcheck.py: a copy of vlm_server_8bit.py that can also
answer two extra kinds of request, for the stop-aware controller.

A request may now carry a "mode" (default "act"):
    "act"        unchanged: NaVILA's normal next-action answer (text)
    "stop_prob"  NaVILA's normal prompt, but instead of generating, return how
                 likely its answer is to start like a stop. NaVILA's answers
                 always start either "I think I should stop ..." or "The next
                 action is ...", so the first token decides. Returns
                 {"stop_prob", "p_stop", "p_act", "top5"}.
    "ask"        same images and instruction, but the last sentence of the
                 prompt ("Analyze this series of images to decide your next
                 action ...") is replaced by request["question"]; returns the
                 generated text.

Normal requests (no "mode") behave exactly like vlm_server_8bit.py, so
navila_eval.py works against this server unchanged.

Run from NaVILA-Bench/scripts, after patch_vlm_server_8bit.py:
    cd ~/go2-sim/NaVILA-Bench/scripts
    python3 /path/to/patch_vlm_server_stopcheck.py
"""

src = open('vlm_server_8bit.py').read()
edits = [
    # 1. Read the optional fields from the request.
    ('''                query = request['query']

                # Process images and generate response
                response = self.process_request(images, query)''',
     '''                query = request['query']
                mode = request.get('mode', 'act')
                question = request.get('question')

                # Process images and generate response
                response = self.process_request(images, query, mode, question)'''),
    # 2. Stop probability from the first generated token.
    ('''    def process_request(self, images, query):''',
     '''    def _first_token_ids(self, word):
        ids = set()
        for variant in (word, " " + word):
            toks = self.tokenizer(variant, add_special_tokens=False).input_ids
            if toks:
                ids.add(toks[0])
        return sorted(ids)

    def _stop_prob(self, input_ids, image_tensor):
        with torch.inference_mode():
            out = self.model.generate(
                input_ids,
                images=[image_tensor],
                do_sample=False,
                temperature=0,
                top_p=None,
                num_beams=1,
                max_new_tokens=1,
                use_cache=True,
                output_scores=True,
                return_dict_in_generate=True,
            )
        probs = torch.softmax(out.scores[0][0].float(), dim=-1)
        p_stop = probs[self._first_token_ids("I")].sum().item()   # "I think I should stop ..."
        p_act = probs[self._first_token_ids("The")].sum().item()  # "The next action is ..."
        top = torch.topk(probs, 5)
        return {
            "stop_prob": p_stop / max(p_stop + p_act, 1e-12),
            "p_stop": p_stop,
            "p_act": p_act,
            "top5": [[self.tokenizer.decode([int(i)]), round(p.item(), 4)] for p, i in zip(top.values, top.indices)],
        }

    def process_request(self, images, query, mode="act", question=None):'''),
    # 3. "ask": keep the images + instruction, swap the final sentence.
    ('''        conv.append_message(conv.roles[0], qs)''',
     '''        if mode == "ask":
            qs = qs.split("Analyze this series of images")[0] + question
        conv.append_message(conv.roles[0], qs)'''),
    # 4. Branch off before normal generation.
    ('''        stopping_criteria = KeywordsStoppingCriteria(keywords, self.tokenizer, input_ids)
''',
     '''        stopping_criteria = KeywordsStoppingCriteria(keywords, self.tokenizer, input_ids)
        if mode == "stop_prob":
            return self._stop_prob(input_ids, image_tensor)
'''),
]
for old, new in edits:
    assert src.count(old) == 1, "not found: " + old
    src = src.replace(old, new)
open('vlm_server_stopcheck.py', 'w').write(src)
print('wrote vlm_server_stopcheck.py')
