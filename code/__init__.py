"""Cognitive Campus Assistant - application package.

Layer map (matches proposal section 7):

    code.nlu          Ingestion      preprocessing and entity extraction
    code.intent_model Learning       TF-IDF + logistic regression intent model
    code.sentiment    Learning       Naive Bayes feedback sentiment model
    code.knowledge    Knowledge      ontology records and answer building
    code.rules_trace  Reasoning      forward chaining (the root rules_trace.py)
    code.explain      Reasoning      backward chaining, "why can I not enroll?"
    code.dialogue     Conversation   session memory, clarification, hand-off
    code.logger       Analytics      chat log for the staff dashboard
    code.forecast     Analytics      volume forecast and staff recommendation
"""
