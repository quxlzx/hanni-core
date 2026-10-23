"""Stable questions shared by generation, training, evaluation and HANNI inference.
Do not change their wording without re-generating/re-evaluating the model.
"""
CAPTURE = {'type':'noul','instructions':'Does this message establish a durable fact, preference, ongoing project decision, or recurring need about the speaker, worth remembering after this conversation? Ignore ordinary questions and hypothetical scenarios.'}
RELEVANCE = {'type':'noul','instructions':'Does the candidate memory provide specific useful context needed to interpret or answer the CURRENT request, beyond merely sharing the same broad topic?'}
RELATION = {'type':'choice','instructions':'How should a new user utterance relate to an existing memory? Choose based on established facts, not speculation.', 'criteria':{
    'supersede':'A new explicit decision contradicts and replaces the same existing fact',
    'add':'A new distinct fact can coexist with the existing fact',
    'ignore':'The new utterance adds no durable user fact',
    'verify':'Ambiguous, hypothetical, contradictory or unclear; ask before changing memory'
}}
IMPORTANCE = {'type':'score','instructions':'How useful will this user information be across future conversations?', 'criteria':['ephemeral or not durable','minor occasional context','important recurring context','high-value long-term preference or ongoing responsibility']}
SENSITIVE = {'type':'noul','instructions':'Does this text contain credentials, private contact/financial/medical information, or other sensitive personal or third-party details requiring restricted storage or sharing?'}
Q = {'capture':CAPTURE,'relevance':RELEVANCE,'relation':RELATION,'importance':IMPORTANCE,'sensitive':SENSITIVE}
