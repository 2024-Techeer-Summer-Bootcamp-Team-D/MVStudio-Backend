from django_elasticsearch_dsl import Document, Index, fields
from django_elasticsearch_dsl.registries import registry
from .models import MusicVideo

# Define the Elasticsearch index
music_video_index = Index('music_video')
@music_video_index.doc_type
class MusicVideoDocument(Document):
    name = fields.TextField(
        analyzer='nori_analyzer',
        fields={
            'raw': fields.KeywordField()
        }
    )

    class Index:
        name = 'music_video'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "nori_analyzer": {
                        "type": "custom",
                        "tokenizer": "nori_tokenizer"
                    }
                },
                "tokenizer": {
                    "nori_tokenizer": {
                        "type": "nori_tokenizer"
                    }
                }
            }
        }
    class Django:
        model = MusicVideo
        fields = [
            'id',
            'subject',
        ]