import json
from pathlib import Path
import tempfile
import unittest
from persistence_router import Config, Router


def response(text='Hello', **message_fields):
    return {'model': 'provider-model', 'choices': [{'message': {'role': 'assistant', 'content': text, **message_fields}}]}


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = Config('agent-a', 'primary', 'fallback')
        self.router = Router(self.config, self.path)
        self.messages = [{'role': 'system', 'content': 'Test system'}, {'role': 'user', 'content': 'Hello'}]

    def call(self, result, **options):
        return self.router.complete(self.messages, transport=lambda *args: result, **options)

    def events(self):
        return [json.loads(x) for x in (self.path/'events.jsonl').read_text().splitlines()]

    def test_switch_only_next_request_and_survives_restart(self):
        calls = []
        def first(endpoint, payload, key):
            calls.append(payload)
            return response("I cannot assist with that request.")
        self.router.complete(self.messages, transport=first)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['model'], 'primary')
        restarted = Router(self.config, self.path)
        restarted.complete(self.messages, transport=lambda ep, p, k: calls.append(p) or response())
        self.assertEqual(calls[1]['model'], 'fallback')
        self.assertEqual(restarted.state['switch_count'], 1)

    def test_normal_response_does_not_switch(self):
        self.call(response('I can help you.'))
        self.assertEqual(self.router.state['active_model'], 'primary')
        self.assertFalse((self.path/'notifications.jsonl').exists())

    def test_explicit_refusal_field(self):
        self.call(response(None, refusal='Refused'))
        self.assertEqual(self.router.state['active_model'], 'fallback')

    def test_fallback_refusal_does_not_retry_or_notify_again(self):
        self.call(response("I cannot help."))
        self.call(response("I cannot help."))
        self.assertEqual(len((self.path/'notifications.jsonl').read_text().splitlines()), 1)
        self.assertEqual(self.router.state['switch_count'], 1)

    def test_input_refusal_and_tool_arguments_do_not_trigger(self):
        self.messages.append({'role':'user', 'content':'I cannot help'})
        self.call(response(None, tool_calls=[{'id':'t1','type':'function','function':{'name':'example','arguments':'I cannot help'}}]))
        self.assertEqual(self.router.state['active_model'], 'primary')

    def test_history_and_tool_fields_preserved(self):
        self.messages.extend([{'role':'assistant','content':None,'tool_calls':[{'id':'t1','type':'function','function':{'name':'x','arguments':'{}'}}]}, {'role':'tool','tool_call_id':'t1','content':'result'}])
        payloads=[]
        self.router.complete(self.messages, transport=lambda ep,p,k: payloads.append(p) or response())
        self.assertEqual(payloads[0]['messages'], self.messages)

    def test_stop_persists_and_blocks_transport(self):
        self.router.stop('Researcher intervention')
        with self.assertRaises(RuntimeError):
            Router(self.config, self.path).complete(self.messages, transport=lambda *a: self.fail('Called after stop'))

    def test_approval_is_logged_without_fabricating_permission(self):
        result=response('Please confirm before proceeding.')
        self.assertEqual(self.call(result),result)
        self.assertIn('approval_requested',[e['type'] for e in self.events()])
        self.assertEqual(self.router.state['active_model'], 'primary')

    def test_errors_logged_without_secrets_or_switch(self):
        def failure(*a):
            raise OSError('secret-test-key')
        with self.assertRaises(OSError):
            self.router.complete(self.messages, transport=failure, api_key='secret-test-key')
        self.assertNotIn('secret-test-key',(self.path/'events.jsonl').read_text())
        self.assertEqual(self.events()[-1]['error_type'], 'OSError')
        self.assertEqual(self.router.state['active_model'], 'primary')

    def test_malformed_provider_response_logs_error(self):
        with self.assertRaises(KeyError):
            self.call({})
        self.assertEqual(self.events()[-1]['type'], 'request_error')

    def test_config_drift_rejected(self):
        with self.assertRaises(ValueError):
            Router(Config('agent-b','primary','fallback'),self.path)

    def test_model_and_stream_override_rejected(self):
        for key, value in [('model','other'),('stream',True),('n',2)]:
            with self.assertRaises(ValueError):
                self.call(response(),**{key:value})

    def test_content_blocks(self):
        self.call(response([{'type':'text','text':'I am unable to comply.'}]))
        self.assertEqual(self.router.state['active_model'],'fallback')

    def test_endpoint_validation(self):
        for endpoint in ['http://example.com/v1/chat/completions','https://user:secret@example.com/api','https://example.com/api?key=secret','https:///bad']:
            with self.assertRaises(ValueError):
                Config('a','p','f',endpoint=endpoint)
        Config('a','p','f',endpoint='http://127.0.0.1:8317/v1/chat/completions')

    def test_invalid_regex_rejected(self):
        import re
        with self.assertRaises(re.error):
            Config('a','p','f',refusal_patterns=('(',))

    def test_event_request_response_link_and_reported_model(self):
        self.call(response())
        events=self.events()
        self.assertEqual(events[0]['request_id'],events[1]['request_id'])
        self.assertEqual(events[1]['requested_model'],'primary')
        self.assertEqual(events[1]['reported_model'],'provider-model')


if __name__ == '__main__':
    unittest.main()
