import { readFile } from 'node:fs/promises';
import { basename } from 'node:path';
import { randomUUID } from 'node:crypto';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';

const input = JSON.parse(await new Response(process.stdin).text());
const key = input.key ?? `quiz-images/${new Date().toISOString().slice(0, 10)}/${randomUUID()}-${basename(input.filePath)}`;
const cacheControl = input.cacheControl ?? 'public, max-age=31536000, immutable';
const client = new S3Client({ region: 'auto', endpoint: input.endpoint, credentials: { accessKeyId: input.accessKeyId, secretAccessKey: input.secretAccessKey } });
await client.send(new PutObjectCommand({ Bucket: input.bucket, Key: key, Body: await readFile(input.filePath), ContentType: input.contentType, ContentDisposition: input.contentDisposition, CacheControl: cacheControl }));
console.log(JSON.stringify({ imageUrl: `${input.publicBaseUrl.replace(/\/$/, '')}/${key}` }));
