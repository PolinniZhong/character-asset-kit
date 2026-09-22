import Vision
import AppKit
import CoreImage

let args = CommandLine.arguments
guard args.count == 3 else { fatalError("usage: subjectmask <input> <output>") }
let inputURL = URL(fileURLWithPath: args[1])
let outputURL = URL(fileURLWithPath: args[2])

guard let img = CIImage(contentsOf: inputURL) else { fatalError("cannot load input") }
let request = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(ciImage: img, options: [:])
try handler.perform([request])
guard let obs = request.results?.first else { fatalError("no subject found") }

let maskPixelBuffer = try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: handler)
let maskImage = CIImage(cvPixelBuffer: maskPixelBuffer)
let clearBG = CIImage(color: CIColor.clear).cropped(to: img.extent)
let filter = CIFilter(name: "CIBlendWithMask")!
filter.setValue(img, forKey: kCIInputImageKey)
filter.setValue(clearBG, forKey: kCIInputBackgroundImageKey)
filter.setValue(maskImage, forKey: kCIInputMaskImageKey)
let cutout = filter.outputImage!.cropped(to: img.extent)

let cs = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CIContext(options: [.workingColorSpace: cs])
let cg = ctx.createCGImage(cutout, from: img.extent, format: .RGBA8, colorSpace: cs)!
let rep = NSBitmapImageRep(cgImage: cg)
guard let png = rep.representation(using: .png, properties: [:]) else { fatalError("png encode failed") }
try png.write(to: outputURL)
print("saved \(outputURL.path)")
