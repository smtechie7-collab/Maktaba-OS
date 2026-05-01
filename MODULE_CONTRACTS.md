# Module Contracts

## Editor Module
**Responsibilities:**
- Render structured document
- Capture user input
- Send commands

**Cannot:**
- Access database directly
- Modify document without engine

## Interlinear Module
**Responsibilities:**
- Manage word bundles
- Maintain alignment

**Cannot:**
- Render UI directly
- Store data independently

## AI Module
**Responsibilities:**
- Generate content
- Suggest edits

**Cannot:**
- Directly modify database
- Bypass validation

## Audio Module
**Responsibilities:**
- Process audio timelines
- Export audio

**Cannot:**
- Modify document content

## Export Module
**Responsibilities:**
- Generate PDF / EPUB

**Cannot:**
- Alter document structure