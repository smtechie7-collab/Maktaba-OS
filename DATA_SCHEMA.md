# Data Schema

## Root Document
```json
{
  "type": "document",
  "children": []
}
```

## Chapter Node
```json
{
  "type": "chapter",
  "title": "string",
  "children": []
}
```

## Paragraph Node
```json
{
  "type": "paragraph",
  "text": "string"
}
```

## Interlinear Block
```json
{
  "type": "interlinear_block",
  "words": [
    {
      "l1": "source",
      "l2": "transliteration",
      "l3": "translation"
    }
  ]
}
```

## Footnote Node
```json
{
  "type": "footnote",
  "content": "string"
}
```